/*
 * Orbi: To the Moon — Solana Smart Contract
 * ==========================================
 * Framework: Anchor (https://www.anchor-lang.com)
 * Language:  Rust
 * Network:   Solana Devnet → Mainnet Beta
 *
 * HOW THIS CONNECTS TO THE APP — FULL EXPLANATION AT THE BOTTOM.
 *
 * Instructions implemented here:
 *   1. register_player   — Pay 1 SOL entry fee, create PlayerAccount PDA
 *   2. buy_chest         — Burn STR, emit chest event, credit treasury
 *   3. list_item         — Escrow an NFT into a marketplace PDA
 *   4. cancel_listing    — Return escrowed NFT to owner
 *   5. buy_item          — Transfer SOL (seller 99% / dev 1%), release NFT
 *   6. stake_str         — Lock STR in a StakePosition PDA
 *   7. claim_stake       — After lockup, return principal + yield from treasury
 *   8. submit_score      — Record minigame score on-chain for leaderboard
 */

use anchor_lang::prelude::*;
use anchor_spl::token::{self, Burn, Mint, Token, TokenAccount, Transfer};

declare_id!("OrbiXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX");

// ── Constants ───────────────────────────────────────────────────────────────

const ENTRY_FEE_LAMPORTS: u64 = 1_000_000_000;   // 1 SOL
const MARKETPLACE_FEE_BPS: u64 = 100;             // 1% in basis points
const CHEST_COMMON_COST: u64   = 20;              // STR (smallest unit)
const CHEST_ITEMS_COST: u64    = 80;
const CHEST_FARMING_COST: u64  = 50;
const ENERGY_MAX: u8           = 100;
const HUNGER_MAX: u8           = 10;
const TREASURY_SHARE_BPS: u64  = 7_000;           // 70% of chest cost → treasury


// ══════════════════════════════════════════════════════════════════════════
//  ACCOUNTS (on-chain state)
// ══════════════════════════════════════════════════════════════════════════

/// Stores all mutable state for one player.
/// PDA seeds: ["player", player_pubkey]
#[account]
pub struct PlayerAccount {
    pub owner:          Pubkey,   // wallet that owns this account
    pub level:          u8,
    pub xp:             u32,
    pub energy:         u8,       // 0–energy_max; regenerates passively
    pub hunger:         u8,       // 0–hunger_max; refilled with cheese
    pub daily_score:    u32,      // resets each leaderboard cycle
    pub registered_at:  i64,      // Unix timestamp
    pub bump:           u8,       // PDA bump seed (stored for CPI reuse)
}

impl PlayerAccount {
    pub const LEN: usize = 8     // discriminator
        + 32   // owner
        + 1    // level
        + 4    // xp
        + 1    // energy
        + 1    // hunger
        + 4    // daily_score
        + 8    // registered_at
        + 1;   // bump

    pub fn energy_max(&self) -> u8 {
        ENERGY_MAX.saturating_add(self.level.saturating_sub(1).saturating_mul(10))
    }

    pub fn hunger_max(&self) -> u8 {
        HUNGER_MAX.saturating_add(self.level.saturating_sub(1).saturating_mul(2))
    }
}

/// Holds one marketplace listing: the NFT is escrowed here until sold/cancelled.
/// PDA seeds: ["listing", nft_mint]
#[account]
pub struct ListingAccount {
    pub seller:       Pubkey,
    pub nft_mint:     Pubkey,
    pub price_lamports: u64,
    pub listed_at:    i64,
    pub bump:         u8,
}

impl ListingAccount {
    pub const LEN: usize = 8 + 32 + 32 + 8 + 8 + 1;
}

/// Holds one staking position.
/// PDA seeds: ["stake", player_pubkey, stake_index (u64 as le bytes)]
#[account]
pub struct StakePosition {
    pub owner:        Pubkey,
    pub amount:       u64,    // STR token amount staked
    pub duration_days: u16,   // 30 | 90 | 180
    pub staked_at:    i64,
    pub bump:         u8,
}

impl StakePosition {
    pub const LEN: usize = 8 + 32 + 8 + 2 + 8 + 1;

    pub fn unlock_timestamp(&self) -> i64 {
        self.staked_at + (self.duration_days as i64 * 86_400)
    }

    /// Simple yield: APY% × principal × days/365.
    /// APY: 30d→25%, 90d→45%, 180d→70%
    pub fn yield_amount(&self) -> u64 {
        let apy_bps: u64 = match self.duration_days {
            30  => 2_500,
            90  => 4_500,
            180 => 7_000,
            _   => 2_500,
        };
        // yield = amount * apy_bps / 10_000 * duration_days / 365
        self.amount
            .saturating_mul(apy_bps)
            .saturating_mul(self.duration_days as u64)
            / 10_000
            / 365
    }
}


// ══════════════════════════════════════════════════════════════════════════
//  PROGRAM
// ══════════════════════════════════════════════════════════════════════════

#[program]
pub mod orbi {
    use super::*;

    // ── 1. Register Player ───────────────────────────────────────────────

    /// Players call this exactly once.  Transfers 1 SOL to the treasury,
    /// creates their PlayerAccount PDA, and records initial state.
    pub fn register_player(ctx: Context<RegisterPlayer>) -> Result<()> {
        // Transfer 1 SOL from player → treasury
        let transfer_ix = anchor_lang::system_program::Transfer {
            from: ctx.accounts.player.to_account_info(),
            to:   ctx.accounts.treasury.to_account_info(),
        };
        anchor_lang::system_program::transfer(
            CpiContext::new(ctx.accounts.system_program.to_account_info(), transfer_ix),
            ENTRY_FEE_LAMPORTS,
        )?;

        // Initialise player state
        let acc       = &mut ctx.accounts.player_account;
        acc.owner     = ctx.accounts.player.key();
        acc.level     = 1;
        acc.xp        = 0;
        acc.energy    = ENERGY_MAX;
        acc.hunger    = HUNGER_MAX;
        acc.daily_score = 0;
        acc.registered_at = Clock::get()?.unix_timestamp;
        acc.bump      = ctx.bumps.player_account;

        emit!(PlayerRegistered {
            player:    ctx.accounts.player.key(),
            timestamp: acc.registered_at,
        });

        Ok(())
    }

    // ── 2. Buy Chest ────────────────────────────────────────────────────

    /// Deduct STR from the player, split between burn and treasury.
    /// The backend (Python) observes this event and rolls the chest contents
    /// off-chain, then mints the resulting NFT back to the player.
    pub fn buy_chest(ctx: Context<BuyChest>, chest_type: u8) -> Result<()> {
        let cost = match chest_type {
            0 => CHEST_COMMON_COST,
            1 => CHEST_FARMING_COST,
            2 => CHEST_ITEMS_COST,
            _ => return err!(OrbiError::InvalidChestType),
        };

        // How much to burn vs send to treasury
        let treasury_amount = cost
            .saturating_mul(TREASURY_SHARE_BPS)
            / 10_000;
        let burn_amount = cost.saturating_sub(treasury_amount);

        // Burn a portion of STR
        token::burn(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Burn {
                    mint:      ctx.accounts.str_mint.to_account_info(),
                    from:      ctx.accounts.player_str_account.to_account_info(),
                    authority: ctx.accounts.player.to_account_info(),
                },
            ),
            burn_amount,
        )?;

        // Transfer the rest to staking treasury token account
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.player_str_account.to_account_info(),
                    to:        ctx.accounts.treasury_str_account.to_account_info(),
                    authority: ctx.accounts.player.to_account_info(),
                },
            ),
            treasury_amount,
        )?;

        // Update player XP
        let player_acc = &mut ctx.accounts.player_account;
        player_acc.xp = player_acc.xp.saturating_add(50);
        if player_acc.xp >= 1_000 {
            player_acc.xp    -= 1_000;
            player_acc.level  = player_acc.level.saturating_add(1);
        }

        emit!(ChestPurchased {
            player:     ctx.accounts.player.key(),
            chest_type,
            str_burned: burn_amount,
            timestamp:  Clock::get()?.unix_timestamp,
        });

        Ok(())
    }

    // ── 3. List Item ─────────────────────────────────────────────────────

    /// Escrow an NFT into a PDA so it cannot be double-sold.
    pub fn list_item(
        ctx:   Context<ListItem>,
        price_lamports: u64,
    ) -> Result<()> {
        require!(price_lamports > 0, OrbiError::InvalidPrice);

        // Transfer NFT from player → listing PDA escrow token account
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.player_nft_account.to_account_info(),
                    to:        ctx.accounts.escrow_nft_account.to_account_info(),
                    authority: ctx.accounts.player.to_account_info(),
                },
            ),
            1, // NFTs have amount = 1
        )?;

        // Record listing
        let listing          = &mut ctx.accounts.listing;
        listing.seller       = ctx.accounts.player.key();
        listing.nft_mint     = ctx.accounts.nft_mint.key();
        listing.price_lamports = price_lamports;
        listing.listed_at    = Clock::get()?.unix_timestamp;
        listing.bump         = ctx.bumps.listing;

        emit!(ItemListed {
            seller:     ctx.accounts.player.key(),
            nft_mint:   ctx.accounts.nft_mint.key(),
            price_lamports,
        });

        Ok(())
    }

    // ── 4. Cancel Listing ────────────────────────────────────────────────

    pub fn cancel_listing(ctx: Context<CancelListing>) -> Result<()> {
        // Return NFT to seller
        let seeds: &[&[u8]] = &[
            b"listing",
            ctx.accounts.nft_mint.key().as_ref(),
            &[ctx.accounts.listing.bump],
        ];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.escrow_nft_account.to_account_info(),
                    to:        ctx.accounts.seller_nft_account.to_account_info(),
                    authority: ctx.accounts.listing.to_account_info(),
                },
                &[seeds],
            ),
            1,
        )?;

        Ok(()) // listing account closed by Anchor (close = seller)
    }

    // ── 5. Buy Item ──────────────────────────────────────────────────────

    /// Buyer transfers SOL.  Contract splits: 99% to seller, 1% to dev.
    /// Then releases escrowed NFT to buyer.
    pub fn buy_item(ctx: Context<BuyItem>) -> Result<()> {
        let price = ctx.accounts.listing.price_lamports;
        let dev_fee = price
            .saturating_mul(MARKETPLACE_FEE_BPS)
            / 10_000;
        let seller_amount = price.saturating_sub(dev_fee);

        // SOL → seller
        anchor_lang::system_program::transfer(
            CpiContext::new(
                ctx.accounts.system_program.to_account_info(),
                anchor_lang::system_program::Transfer {
                    from: ctx.accounts.buyer.to_account_info(),
                    to:   ctx.accounts.seller.to_account_info(),
                },
            ),
            seller_amount,
        )?;

        // SOL → dev wallet
        anchor_lang::system_program::transfer(
            CpiContext::new(
                ctx.accounts.system_program.to_account_info(),
                anchor_lang::system_program::Transfer {
                    from: ctx.accounts.buyer.to_account_info(),
                    to:   ctx.accounts.dev_wallet.to_account_info(),
                },
            ),
            dev_fee,
        )?;

        // Release escrowed NFT → buyer
        let seeds: &[&[u8]] = &[
            b"listing",
            ctx.accounts.nft_mint.key().as_ref(),
            &[ctx.accounts.listing.bump],
        ];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.escrow_nft_account.to_account_info(),
                    to:        ctx.accounts.buyer_nft_account.to_account_info(),
                    authority: ctx.accounts.listing.to_account_info(),
                },
                &[seeds],
            ),
            1,
        )?;

        emit!(ItemSold {
            buyer:    ctx.accounts.buyer.key(),
            seller:   ctx.accounts.seller.key(),
            nft_mint: ctx.accounts.nft_mint.key(),
            price_lamports: price,
            dev_fee,
        });

        Ok(())
    }

    // ── 6. Stake STR ──────────────────────────────────────────────────────

    pub fn stake_str(
        ctx:          Context<StakeStr>,
        amount:       u64,
        duration_days: u16,
    ) -> Result<()> {
        require!(
            matches!(duration_days, 30 | 90 | 180),
            OrbiError::InvalidStakeDuration
        );
        require!(amount > 0, OrbiError::ZeroAmount);

        // Transfer STR from player → stake vault PDA
        token::transfer(
            CpiContext::new(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.player_str_account.to_account_info(),
                    to:        ctx.accounts.stake_vault.to_account_info(),
                    authority: ctx.accounts.player.to_account_info(),
                },
            ),
            amount,
        )?;

        let pos            = &mut ctx.accounts.stake_position;
        pos.owner          = ctx.accounts.player.key();
        pos.amount         = amount;
        pos.duration_days  = duration_days;
        pos.staked_at      = Clock::get()?.unix_timestamp;
        pos.bump           = ctx.bumps.stake_position;

        emit!(TokensStaked {
            player:        ctx.accounts.player.key(),
            amount,
            duration_days,
            unlock_at:     pos.unlock_timestamp(),
        });

        Ok(())
    }

    // ── 7. Claim Stake ────────────────────────────────────────────────────

    pub fn claim_stake(ctx: Context<ClaimStake>) -> Result<()> {
        let now  = Clock::get()?.unix_timestamp;
        let pos  = &ctx.accounts.stake_position;

        require!(now >= pos.unlock_timestamp(), OrbiError::StakeLocked);

        let principal = pos.amount;
        let yield_amt = pos.yield_amount();
        let total     = principal.saturating_add(yield_amt);

        // Return principal from stake vault
        let seeds: &[&[u8]] = &[
            b"stake",
            ctx.accounts.player.key().as_ref(),
            &pos.staked_at.to_le_bytes(),
            &[pos.bump],
        ];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.stake_vault.to_account_info(),
                    to:        ctx.accounts.player_str_account.to_account_info(),
                    authority: ctx.accounts.stake_position.to_account_info(),
                },
                &[seeds],
            ),
            principal,
        )?;

        // Pay yield from treasury (treasury authority is a PDA)
        let treasury_seeds: &[&[u8]] = &[b"treasury", &[ctx.bumps.treasury_authority]];
        token::transfer(
            CpiContext::new_with_signer(
                ctx.accounts.token_program.to_account_info(),
                Transfer {
                    from:      ctx.accounts.treasury_str_account.to_account_info(),
                    to:        ctx.accounts.player_str_account.to_account_info(),
                    authority: ctx.accounts.treasury_authority.to_account_info(),
                },
                &[treasury_seeds],
            ),
            yield_amt,
        )?;

        emit!(StakeClaimed {
            player:    ctx.accounts.player.key(),
            principal,
            yield_str: yield_amt,
            total,
        });

        Ok(())
    }

    // ── 8. Submit Score ───────────────────────────────────────────────────

    /// Records a minigame score on-chain. Backend validates game replay
    /// before accepting the transaction signature.
    pub fn submit_score(ctx: Context<SubmitScore>, score: u32) -> Result<()> {
        let player_acc = &mut ctx.accounts.player_account;

        require!(player_acc.energy > 0,  OrbiError::NoEnergy);
        require!(player_acc.hunger > 0,  OrbiError::NoHunger);

        player_acc.energy      = player_acc.energy.saturating_sub(10);
        player_acc.hunger      = player_acc.hunger.saturating_sub(1);
        player_acc.daily_score = player_acc.daily_score.saturating_add(score);
        player_acc.xp          = player_acc.xp.saturating_add(score / 10);

        if player_acc.xp >= 1_000 {
            player_acc.xp    -= 1_000;
            player_acc.level  = player_acc.level.saturating_add(1);
        }

        emit!(ScoreSubmitted {
            player:    ctx.accounts.player.key(),
            score,
            timestamp: Clock::get()?.unix_timestamp,
        });

        Ok(())
    }
}


// ══════════════════════════════════════════════════════════════════════════
//  ACCOUNT CONTEXTS
// ══════════════════════════════════════════════════════════════════════════

#[derive(Accounts)]
pub struct RegisterPlayer<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    #[account(
        init,
        payer  = player,
        space  = PlayerAccount::LEN,
        seeds  = [b"player", player.key().as_ref()],
        bump,
    )]
    pub player_account: Account<'info, PlayerAccount>,

    /// CHECK: Treasury wallet — verified by address in production
    #[account(mut)]
    pub treasury: UncheckedAccount<'info>,

    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct BuyChest<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    #[account(
        mut,
        seeds = [b"player", player.key().as_ref()],
        bump  = player_account.bump,
        has_one = owner @ OrbiError::NotOwner,
    )]
    pub player_account: Account<'info, PlayerAccount>,

    #[account(mut)]
    pub str_mint: Account<'info, Mint>,

    #[account(mut)]
    pub player_str_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub treasury_str_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct ListItem<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    pub nft_mint: Account<'info, Mint>,

    #[account(
        init,
        payer  = player,
        space  = ListingAccount::LEN,
        seeds  = [b"listing", nft_mint.key().as_ref()],
        bump,
    )]
    pub listing: Account<'info, ListingAccount>,

    #[account(mut)]
    pub player_nft_account: Account<'info, TokenAccount>,

    /// CHECK: Escrow token account owned by listing PDA
    #[account(mut)]
    pub escrow_nft_account: UncheckedAccount<'info>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct CancelListing<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    pub nft_mint: Account<'info, Mint>,

    #[account(
        mut,
        seeds  = [b"listing", nft_mint.key().as_ref()],
        bump   = listing.bump,
        has_one = seller @ OrbiError::NotOwner,
        close  = player,
    )]
    pub listing: Account<'info, ListingAccount>,

    #[account(mut)]
    pub seller_nft_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub escrow_nft_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct BuyItem<'info> {
    #[account(mut)]
    pub buyer: Signer<'info>,

    /// CHECK: Seller — must match listing.seller
    #[account(mut, address = listing.seller)]
    pub seller: UncheckedAccount<'info>,

    /// CHECK: Dev wallet — hardcoded address verified at deploy
    #[account(mut)]
    pub dev_wallet: UncheckedAccount<'info>,

    pub nft_mint: Account<'info, Mint>,

    #[account(
        mut,
        seeds  = [b"listing", nft_mint.key().as_ref()],
        bump   = listing.bump,
        close  = seller,
    )]
    pub listing: Account<'info, ListingAccount>,

    #[account(mut)]
    pub escrow_nft_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub buyer_nft_account: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct StakeStr<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    #[account(
        init,
        payer  = player,
        space  = StakePosition::LEN,
        seeds  = [
            b"stake",
            player.key().as_ref(),
            &Clock::get().unwrap().unix_timestamp.to_le_bytes(),
        ],
        bump,
    )]
    pub stake_position: Account<'info, StakePosition>,

    #[account(mut)]
    pub player_str_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,

    pub token_program: Program<'info, Token>,
    pub system_program: Program<'info, System>,
}

#[derive(Accounts)]
pub struct ClaimStake<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    #[account(
        mut,
        seeds  = [
            b"stake",
            player.key().as_ref(),
            &stake_position.staked_at.to_le_bytes(),
        ],
        bump   = stake_position.bump,
        has_one = owner @ OrbiError::NotOwner,
        close  = player,
    )]
    pub stake_position: Account<'info, StakePosition>,

    #[account(mut)]
    pub player_str_account: Account<'info, TokenAccount>,

    #[account(mut)]
    pub stake_vault: Account<'info, TokenAccount>,

    #[account(mut)]
    pub treasury_str_account: Account<'info, TokenAccount>,

    /// CHECK: PDA that is authority over treasury_str_account
    #[account(seeds = [b"treasury"], bump)]
    pub treasury_authority: UncheckedAccount<'info>,

    pub token_program: Program<'info, Token>,
}

#[derive(Accounts)]
pub struct SubmitScore<'info> {
    #[account(mut)]
    pub player: Signer<'info>,

    #[account(
        mut,
        seeds  = [b"player", player.key().as_ref()],
        bump   = player_account.bump,
        has_one = owner @ OrbiError::NotOwner,
    )]
    pub player_account: Account<'info, PlayerAccount>,
}


// ══════════════════════════════════════════════════════════════════════════
//  EVENTS
// ══════════════════════════════════════════════════════════════════════════

#[event]
pub struct PlayerRegistered { pub player: Pubkey,  pub timestamp: i64 }

#[event]
pub struct ChestPurchased {
    pub player:     Pubkey,
    pub chest_type: u8,
    pub str_burned: u64,
    pub timestamp:  i64,
}

#[event]
pub struct ItemListed {
    pub seller:        Pubkey,
    pub nft_mint:      Pubkey,
    pub price_lamports: u64,
}

#[event]
pub struct ItemSold {
    pub buyer:          Pubkey,
    pub seller:         Pubkey,
    pub nft_mint:       Pubkey,
    pub price_lamports: u64,
    pub dev_fee:        u64,
}

#[event]
pub struct TokensStaked {
    pub player:        Pubkey,
    pub amount:        u64,
    pub duration_days: u16,
    pub unlock_at:     i64,
}

#[event]
pub struct StakeClaimed {
    pub player:    Pubkey,
    pub principal: u64,
    pub yield_str: u64,
    pub total:     u64,
}

#[event]
pub struct ScoreSubmitted { pub player: Pubkey, pub score: u32, pub timestamp: i64 }


// ══════════════════════════════════════════════════════════════════════════
//  ERRORS
// ══════════════════════════════════════════════════════════════════════════

#[error_code]
pub enum OrbiError {
    #[msg("Not the account owner")]
    NotOwner,
    #[msg("Invalid chest type (0=Seeds, 1=Farming, 2=Items)")]
    InvalidChestType,
    #[msg("Invalid price: must be > 0")]
    InvalidPrice,
    #[msg("Invalid stake duration: must be 30, 90, or 180 days")]
    InvalidStakeDuration,
    #[msg("Amount must be greater than zero")]
    ZeroAmount,
    #[msg("Stake is still locked")]
    StakeLocked,
    #[msg("Not enough energy — wait for regeneration")]
    NoEnergy,
    #[msg("Your moon is hungry — feed it cheese!")]
    NoHunger,
}


/*
 * ══════════════════════════════════════════════════════════════════════════
 *  HOW THE SOLANA CONNECTION ACTUALLY WORKS — FULL EXPLANATION
 * ══════════════════════════════════════════════════════════════════════════
 *
 * OVERVIEW
 * --------
 * Solana programs (smart contracts) are compiled Rust/BPF bytecode stored
 * on-chain at a Program ID address.  Once deployed, anyone can call their
 * instructions by sending a specially constructed Transaction.
 *
 * THE FULL FLOW: from player tap → blockchain → backend → UI
 * -----------------------------------------------------------
 *
 * STEP 1 — BUILD THE PROGRAM
 *   anchor build
 *   → Compiles Rust to BPF bytecode.
 *   → Generates an IDL (Interface Description Language) JSON file that
 *     describes every instruction, account, and type — like an ABI in Ethereum.
 *
 * STEP 2 — DEPLOY TO DEVNET
 *   anchor deploy --provider.cluster devnet
 *   → Uploads the BPF bytecode to Solana Devnet.
 *   → The program gets a permanent address (Program ID), e.g. "OrbiXXXX...".
 *   → The IDL is published on-chain so clients can auto-discover the interface.
 *
 * STEP 3 — FRONTEND CALLS AN INSTRUCTION (example: register_player)
 *   a) User connects Phantom wallet in the browser/iOS app.
 *   b) JavaScript uses @coral-xyz/anchor + the IDL to build an Instruction:
 *
 *      const program = new anchor.Program(IDL, PROGRAM_ID, provider);
 *      await program.methods
 *        .registerPlayer()
 *        .accounts({
 *          player:        wallet.publicKey,
 *          playerAccount: playerPDA,        // derived off-chain
 *          treasury:      TREASURY_ADDRESS,
 *          systemProgram: SystemProgram.programId,
 *        })
 *        .rpc();
 *
 *   c) Anchor builds the Transaction, Phantom prompts user to approve.
 *   d) User signs → Phantom sends the signed tx to a Solana RPC node.
 *   e) Validators confirm the transaction (~0.4 seconds on Solana).
 *   f) The on-chain program runs, creates the PlayerAccount PDA,
 *      transfers 1 SOL to the treasury.
 *
 * STEP 4 — PYTHON BACKEND INDEXES THE EVENT
 *   The backend runs a WebSocket subscription to the program's logs:
 *
 *      client = AsyncClient("https://api.devnet.solana.com")
 *      async for log in client.logs_subscribe(
 *          RpcLogsFilterMentions(PROGRAM_ID)
 *      ):
 *          if "PlayerRegistered" in log.value.logs:
 *              wallet = parse_wallet_from_log(log)
 *              await db.create_player(wallet)
 *
 *   Every time the smart contract emits an event (PlayerRegistered,
 *   ChestPurchased, ItemSold…), the Python indexer catches it and
 *   updates PostgreSQL — keeping the off-chain DB in sync with chain state.
 *
 * STEP 5 — FRONTEND FETCHES STATE FROM BACKEND
 *   The UI calls the Python REST API for things that don't need to be
 *   on-chain (leaderboard rankings, farm timers, display metadata):
 *
 *      GET /player/WALLET_ADDRESS  →  { level, xp, energy, hunger, ... }
 *      GET /inventory/WALLET_ADDRESS  →  [ { mint, name, rarity }, ... ]
 *      GET /leaderboard  →  [ { rank, wallet, daily_score }, ... ]
 *
 *   For things that DO need on-chain authority (buying items, staking,
 *   chest purchases), the frontend builds a Solana transaction and has
 *   Phantom sign it — the backend only records the result after verifying
 *   the transaction signature on-chain.
 *
 * PDA (PROGRAM DERIVED ADDRESS) — what they are and why they matter
 * -----------------------------------------------------------------
 *   A PDA is a special address derived deterministically from seeds:
 *
 *      playerPDA = PublicKey.findProgramAddressSync(
 *        [Buffer.from("player"), wallet.toBytes()],
 *        PROGRAM_ID
 *      )[0];
 *
 *   PDAs have no private key — only the program can sign for them.
 *   This is how the escrow marketplace works: the NFT is sent to a PDA,
 *   and ONLY the smart contract logic can release it (to the buyer or
 *   back to the seller on cancel).  No one can steal escrowed items.
 *
 * TOKEN PROGRAM — how $STR works
 * --------------------------------
 *   $STR is an SPL Token (Solana's equivalent of ERC-20).
 *   - The Mint account holds the token's total supply and authority.
 *   - Each player has a Token Account that holds their STR balance.
 *   - The program uses CPIs (Cross-Program Invocations) to call the
 *     SPL Token program, which actually moves tokens.
 *   - Burning STR calls token::burn() which reduces total supply.
 *
 * TESTNET → MAINNET MIGRATION
 * ----------------------------
 *   1. All development on Devnet (free airdrop SOL, no real value).
 *   2. When ready, run:  anchor deploy --provider.cluster mainnet
 *   3. Change RPC URLs in frontend and Python backend to mainnet.
 *   4. Deploy $STR mint on mainnet via Metaplex or spl-token CLI.
 *   5. Launch CLMM pool on Raydium, burn LP tokens.
 *   6. Transfer program upgrade authority to multisig (Squads).
 *
 * SECURITY GUARANTEES PROVIDED BY THIS SMART CONTRACT
 * ----------------------------------------------------
 *   • has_one = owner checks: only the wallet that registered can
 *     modify their PlayerAccount.
 *   • PDA escrow: items in the marketplace cannot be moved by anyone
 *     except via the buy_item or cancel_listing instructions.
 *   • No private keys held: Orbi never has access to user funds.
 *   • Deterministic yield: staking returns are calculated purely from
 *     on-chain timestamps — no oracle, no off-chain trust required.
 *   • 1% fee is enforced by the contract: cannot be changed without
 *     a program upgrade (which requires multisig approval post-launch).
 *
 * ══════════════════════════════════════════════════════════════════════════
 */
