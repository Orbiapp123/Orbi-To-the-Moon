from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

# Color palette
DARK_BG = colors.HexColor('#0a0a1a')
PURPLE = colors.HexColor('#7c3aed')
LIGHT_PURPLE = colors.HexColor('#a78bfa')
WHITE = colors.white
GREY = colors.HexColor('#94a3b8')
DARK_GREY = colors.HexColor('#1e1e3a')

doc = SimpleDocTemplate(
    "/sessions/festive-adoring-bell/mnt/outputs/Orbi_Whitepaper.pdf",
    pagesize=letter,
    rightMargin=0.75*inch,
    leftMargin=0.75*inch,
    topMargin=0.75*inch,
    bottomMargin=0.75*inch
)

styles = getSampleStyleSheet()

# Custom styles
title_style = ParagraphStyle('Title', parent=styles['Normal'],
    fontSize=32, textColor=WHITE, spaceAfter=6, alignment=TA_CENTER, fontName='Helvetica-Bold')

subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'],
    fontSize=14, textColor=LIGHT_PURPLE, spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica')

h1_style = ParagraphStyle('H1', parent=styles['Normal'],
    fontSize=18, textColor=LIGHT_PURPLE, spaceBefore=20, spaceAfter=8, fontName='Helvetica-Bold')

h2_style = ParagraphStyle('H2', parent=styles['Normal'],
    fontSize=13, textColor=WHITE, spaceBefore=14, spaceAfter=6, fontName='Helvetica-Bold')

body_style = ParagraphStyle('Body', parent=styles['Normal'],
    fontSize=10, textColor=GREY, spaceAfter=8, leading=16, alignment=TA_JUSTIFY, fontName='Helvetica')

body_white = ParagraphStyle('BodyWhite', parent=styles['Normal'],
    fontSize=10, textColor=WHITE, spaceAfter=8, leading=16, alignment=TA_JUSTIFY, fontName='Helvetica')

label_style = ParagraphStyle('Label', parent=styles['Normal'],
    fontSize=9, textColor=LIGHT_PURPLE, spaceAfter=2, fontName='Helvetica-Bold')

small_grey = ParagraphStyle('SmallGrey', parent=styles['Normal'],
    fontSize=8, textColor=GREY, spaceAfter=4, alignment=TA_CENTER, fontName='Helvetica')

def bg_canvas(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
    # Subtle purple top bar
    canvas.setFillColor(PURPLE)
    canvas.rect(0, letter[1]-4, letter[0], 4, fill=1, stroke=0)
    # Page number
    canvas.setFillColor(GREY)
    canvas.setFont('Helvetica', 8)
    canvas.drawCentredString(letter[0]/2, 0.4*inch, f"Orbi: To the Moon  |  Whitepaper v1.0  |  Page {doc.page}")
    canvas.restoreState()

story = []

# ── COVER ──────────────────────────────────────────────────────────────────
story.append(Spacer(1, 1.2*inch))
story.append(Paragraph("ORBI", title_style))
story.append(Paragraph("To the Moon", ParagraphStyle('TitleSub', parent=title_style, fontSize=20, textColor=LIGHT_PURPLE)))
story.append(Spacer(1, 0.2*inch))
story.append(HRFlowable(width="60%", thickness=1, color=PURPLE, hAlign='CENTER'))
story.append(Spacer(1, 0.2*inch))
story.append(Paragraph("Official Whitepaper — v1.0", subtitle_style))
story.append(Paragraph("April 2026", small_grey))
story.append(Spacer(1, 0.5*inch))

cover_desc = ParagraphStyle('CoverDesc', parent=body_style, alignment=TA_CENTER, fontSize=11, textColor=WHITE, leading=18)
story.append(Paragraph(
    "A casual mobile game on Solana combining accessible gameplay with real on-chain ownership, "
    "a native token economy, and a community-driven governance model.",
    cover_desc))
story.append(Spacer(1, 0.3*inch))
story.append(HRFlowable(width="40%", thickness=1, color=DARK_GREY, hAlign='CENTER'))
story.append(Spacer(1, 0.15*inch))
story.append(Paragraph("orbiapp123.github.io  |  @Orbi_solana  |  discord.gg/JGgGFaPK", small_grey))
story.append(PageBreak())

# ── TABLE OF CONTENTS ──────────────────────────────────────────────────────
story.append(Paragraph("Table of Contents", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))

toc_data = [
    ["1.", "Abstract", "3"],
    ["2.", "The Problem", "3"],
    ["3.", "What is Orbi?", "3"],
    ["4.", "Game Mechanics", "4"],
    ["5.", "Tokenomics: $STR", "5"],
    ["6.", "Token Allocation", "5"],
    ["7.", "Revenue Streams", "6"],
    ["8.", "Roadmap", "6"],
    ["9.", "Governance", "7"],
    ["10.", "Target Audience", "7"],
    ["11.", "KPIs & Growth Targets", "7"],
    ["12.", "Team", "8"],
    ["13.", "Legal Disclaimer", "8"],
]

toc_style = TableStyle([
    ('TEXTCOLOR', (0,0), (-1,-1), GREY),
    ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
    ('FONTSIZE', (0,0), (-1,-1), 10),
    ('ROWBACKGROUNDS', (0,0), (-1,-1), [DARK_BG, DARK_GREY]),
    ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ('LEFTPADDING', (0,0), (0,-1), 8),
    ('TEXTCOLOR', (1,0), (1,-1), WHITE),
    ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
    ('ALIGN', (2,0), (2,-1), 'RIGHT'),
    ('TEXTCOLOR', (2,0), (2,-1), LIGHT_PURPLE),
])
toc_table = Table(toc_data, colWidths=[0.4*inch, 5.5*inch, 0.5*inch])
toc_table.setStyle(toc_style)
story.append(toc_table)
story.append(PageBreak())

# ── 1. ABSTRACT ────────────────────────────────────────────────────────────
story.append(Paragraph("1. Abstract", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi is a casual mobile game built on the Solana blockchain that bridges the gap between mainstream mobile gaming and the Web3 economy. "
    "Players manage a Moon character, compete in daily minigames, farm resources, open chests, and trade items in a peer-to-peer marketplace — "
    "all while owning their in-game assets on-chain. The native token $STR powers the game economy through staking, chest purchases, and leaderboard rewards. "
    "Orbi's design philosophy is simple: make a game that people genuinely want to play first, and layer real economic value on top.",
    body_style))

# ── 2. THE PROBLEM ─────────────────────────────────────────────────────────
story.append(Paragraph("2. The Problem", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "The gaming market is split between two worlds that do not yet talk to each other. Traditional mobile games are accessible and engaging, "
    "but players spend real money on items they never truly own — when a game shuts down, everything disappears. "
    "Web3 games promise ownership but overwhelm casual players with complex mechanics, high entry costs, and poor gameplay loops. "
    "Existing examples illustrate the risk: Axie Infinity required 3.5 ETH to enter and created an unsustainable token economy that eventually collapsed. "
    "Orbi is designed from the ground up to avoid these pitfalls — low entry cost (1 SOL), genuine gameplay first, and a deflationary token model "
    "tied directly to in-game activity.",
    body_style))

# ── 3. WHAT IS ORBI? ───────────────────────────────────────────────────────
story.append(Paragraph("3. What is Orbi?", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi is a casual mobile game available on iOS (with Android expansion planned), built on the Solana blockchain. "
    "Players pay a one-time entry fee of 1 SOL to mint a non-transferable Moon character. From there, they play daily minigames, "
    "manage a farming system, open chests to acquire items of varying rarity, and trade those items in the Orbi Marketplace. "
    "The game uses a native token, $STR (ticker: STR), for chest purchases, staking rewards, and leaderboard payouts. "
    "The marketplace operates in SOL, with a 1% developer fee on every transaction. "
    "Orbi is built on Solana for its speed, low transaction fees, and growing gaming ecosystem.",
    body_style))

# ── 4. GAME MECHANICS ──────────────────────────────────────────────────────
story.append(Paragraph("4. Game Mechanics", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))

story.append(Paragraph("Character System", h2_style))
story.append(Paragraph(
    "Each player's Moon character is non-transferable and tied to their wallet, forcing organic progression and rewarding early adopters. "
    "The character has two core bars: an Energy Bar (playable hours, e.g. 3 of every 10 hours) and a Hunger Bar (number of games playable per session). "
    "When bars deplete, game features grey out — a deliberate mechanic that limits bot activity and maintains fair play.",
    body_style))

story.append(Paragraph("Minigames", h2_style))
story.append(Paragraph(
    "Orbi is a hub for simple, fast-paced minigames themed around its cosmic universe. Games are updated regularly to maintain engagement. "
    "Players earn $STR based on daily leaderboard performance, with a tiered payout system: top performers earn the most, "
    "while lower-ranked players still earn enough to progress. The number of games playable per session is governed by the Hunger Bar.",
    body_style))

story.append(Paragraph("Farming", h2_style))
story.append(Paragraph(
    "Players start with a basic cow (non-transferable) and can grow wheat, feed cows, produce milk, and manufacture cheese. "
    "Cheese replenishes the Hunger Bar, keeping long-term players engaged with the game economy. "
    "Seed chests can be purchased to expand the farm, and the duration of farming steps varies with the rarity of the player's cow and their level.",
    body_style))

story.append(Paragraph("Chests & Items", h2_style))
story.append(Paragraph(
    "Players can purchase chests with $STR. Chest types include Farming Chests (cows), Seed Chests (fixed seeds), "
    "and Item Chests (accessories, cows, potions, cheese, etc). Items come in varying rarity tiers — Common, Uncommon, Rare, Epic, Cosmic — "
    "and can be equipped for attribute boosts, used in-game, or sold in the Marketplace.",
    body_style))

story.append(Paragraph("Levelling", h2_style))
story.append(Paragraph(
    "Players gain XP through opening chests, playing minigames, staking tokens, and farming. "
    "Higher levels unlock greater Energy and Hunger capacity, exclusive chests, and small milestone rewards such as common accessories. "
    "The non-transferable character model ensures all progression is earned, not bought.",
    body_style))

story.append(PageBreak())

# ── 5. TOKENOMICS ──────────────────────────────────────────────────────────
story.append(Paragraph("5. Tokenomics: $STR", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "$STR (STAR) is Orbi's native in-game token. The decision to build around a native token rather than use SOL directly was deliberate. "
    "Burning SOL would be unsustainable and expensive for the development team, whereas $STR gives full control over supply — "
    "allowing the team to manage inflation, adjust minigame rewards, and maintain price stability over time. "
    "Staking rewards are funded directly by chest purchase revenue into the treasury, meaning the health of the token is "
    "tied directly to the health of the game. The more players engage, the stronger the rewards.",
    body_style))

story.append(Paragraph("Token Sinks", h2_style))
sinks = [
    ["Chest Purchases", "Primary $STR sink. Burns a portion of each transaction and routes the rest to the staking treasury."],
    ["Staking Locks", "Tokens removed from circulation for fixed periods (30/90/180 days), reducing sell pressure."],
    ["Leaderboard Rewards", "Distributed daily from a fixed per-day $STR budget — not minted fresh, preserving supply."],
    ["Dev Supply Control", "Team can adjust minigame reward rates per epoch to stabilise $STR price without touching total supply."],
]
sink_table = Table(sinks, colWidths=[1.8*inch, 4.6*inch])
sink_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,-1), DARK_GREY),
    ('BACKGROUND', (1,0), (1,-1), DARK_BG),
    ('TEXTCOLOR', (0,0), (0,-1), LIGHT_PURPLE),
    ('TEXTCOLOR', (1,0), (1,-1), GREY),
    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ('FONTNAME', (1,0), (1,-1), 'Helvetica'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('TOPPADDING', (0,0), (-1,-1), 7),
    ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, DARK_GREY),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story.append(sink_table)

story.append(Paragraph("Token Launch", h2_style))
story.append(Paragraph(
    "The initial $STR release uses a Concentrated Liquidity Market Maker (CLMM) pool on Raydium. "
    "This allows the team to set the initial price range and market cap without deploying large amounts of capital. "
    "LP tokens are burned immediately on-chain — provably locked liquidity, verifiable by anyone, eliminating rug pull risk. "
    "1–3 days post-launch, a Dynamic Liquidity Market Maker (DLMM) pool opens on Meteora, allowing third parties and players "
    "to add their own liquidity and earn trading fees, deepening the market organically.",
    body_style))

# ── 6. TOKEN ALLOCATION ────────────────────────────────────────────────────
story.append(Paragraph("6. Token Allocation", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))

alloc_data = [
    ["Allocation", "Percentage", "Purpose"],
    ["Staking Treasury", "40%", "Rewards for token stakers, funded by chest sales"],
    ["Public Launch (CLMM)", "30%", "Initial liquidity on Raydium with locked LP tokens"],
    ["Team & Development", "15%", "Developer incentives and ongoing build costs"],
    ["Marketing & Airdrop", "10%", "Community growth, influencer campaigns, early adopter rewards"],
    ["Reserve", "5%", "Contingency fund for unforeseen operational needs"],
]
alloc_table = Table(alloc_data, colWidths=[2*inch, 1.2*inch, 3.2*inch])
alloc_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), PURPLE),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [DARK_GREY, DARK_BG]),
    ('TEXTCOLOR', (0,1), (-1,-1), GREY),
    ('TEXTCOLOR', (1,1), (1,-1), LIGHT_PURPLE),
    ('FONTNAME', (1,1), (1,-1), 'Helvetica-Bold'),
    ('TOPPADDING', (0,0), (-1,-1), 7),
    ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, DARK_GREY),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story.append(alloc_table)
story.append(PageBreak())

# ── 7. REVENUE STREAMS ─────────────────────────────────────────────────────
story.append(Paragraph("7. Revenue Streams", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi's revenue model is built around three complementary streams that strengthen each other as the player base grows.",
    body_style))

story.append(Paragraph("Sign-Up Fee (1 SOL per player)", h2_style))
story.append(Paragraph(
    "Every new player pays 1 SOL to enter the game. This is a direct, scalable revenue stream — at 1,000 players and $150/SOL, "
    "that represents approximately $150,000 in entry revenue alone. As the player base grows, this compounds significantly.",
    body_style))

story.append(Paragraph("Marketplace Trading Fee (1% per trade)", h2_style))
story.append(Paragraph(
    "Every peer-to-peer trade in the Orbi Marketplace generates a 1% fee paid to the developer wallet. "
    "Revenue here scales with trade volume, not just player count. At 2,000 SOL in volume, that is $3,000 in direct fee revenue — "
    "a figure that grows as item values appreciate and trading activity increases.",
    body_style))

story.append(Paragraph("DLMM Liquidity Pool (Meteora)", h2_style))
story.append(Paragraph(
    "By allocating a portion of tokens to the DLMM pool on Meteora, Orbi earns trading fees passively. "
    "As the token gains utility and the player base grows, organic trading volume increases — meaning fee revenue compounds "
    "without requiring additional direct effort from the team.",
    body_style))

# ── 8. ROADMAP ─────────────────────────────────────────────────────────────
story.append(Paragraph("8. Roadmap", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))

roadmap = [
    ["Stage", "Timeline", "Milestones"],
    ["Stage 1 — Foundation", "Q1 2026", "Core game loop built, Solana smart contracts deployed to testnet, internal alpha testing"],
    ["Stage 2 — Devnet", "Q2 2026", "Devnet launch, X and Discord communities established, TikTok/Instagram content begins, beta feedback loop"],
    ["Stage 3 — Mainnet", "Q3 2026", "Mainnet launch on Solana, $STR token launch via Raydium CLMM, LP tokens burned, DLMM pool opens"],
    ["Stage 4 — Community", "Q3–Q4 2026", "Referral system, expanded minigame library, clan system introduced, first community governance votes"],
    ["Stage 5 — Ecosystem", "Q4 2026+", "Platform maturity: 1,000+ players, $500K+ market cap, 2,000+ SOL marketplace volume, third-party community tools"],
]
roadmap_table = Table(roadmap, colWidths=[1.6*inch, 1.1*inch, 3.7*inch])
roadmap_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), PURPLE),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [DARK_GREY, DARK_BG]),
    ('TEXTCOLOR', (0,1), (0,-1), LIGHT_PURPLE),
    ('FONTNAME', (0,1), (0,-1), 'Helvetica-Bold'),
    ('TEXTCOLOR', (1,1), (-1,-1), GREY),
    ('TOPPADDING', (0,0), (-1,-1), 7),
    ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, DARK_GREY),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story.append(roadmap_table)
story.append(PageBreak())

# ── 9. GOVERNANCE ──────────────────────────────────────────────────────────
story.append(Paragraph("9. Governance", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi is structured as a traditional legal company, providing clear accountability, IP protection, and regulatory compliance. "
    "However, it incorporates community governance mechanics drawn from the DAO model to keep players genuinely invested in the platform's direction. "
    "Token holders can vote on new game additions and reward allocation structures. Voting power is determined by two factors: "
    "the amount of $STR held, and the player's in-game level. This dual-factor model prevents pure whale dominance — "
    "active, engaged players carry meaningful influence alongside large token holders. "
    "The development team retains weighted control to ensure product quality and stability.",
    body_style))

# ── 10. TARGET AUDIENCE ────────────────────────────────────────────────────
story.append(Paragraph("10. Target Audience", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi is designed to appeal across three distinct user profiles simultaneously:",
    body_style))

audience = [
    ["The Student", "Age 19–24", "Crypto-curious but intimidated. Attracted by simple gameplay, low entry cost, and the potential for earnings without needing prior Web3 experience."],
    ["The Commuter", "Age 25–34", "Time-poor and progress-driven. Values structured daily loops, leaderboard competition, and farm mechanics that fit a busy routine."],
    ["The Degen", "Age 22–35", "On-chain native. Evaluating $STR staking yields, marketplace arbitrage opportunities, and early token entry potential."],
]
aud_table = Table(audience, colWidths=[1.3*inch, 0.9*inch, 4.2*inch])
aud_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,-1), DARK_GREY),
    ('TEXTCOLOR', (0,0), (0,-1), LIGHT_PURPLE),
    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ('TEXTCOLOR', (1,0), (1,-1), GREY),
    ('FONTNAME', (1,0), (1,-1), 'Helvetica-Oblique'),
    ('TEXTCOLOR', (2,0), (2,-1), GREY),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('TOPPADDING', (0,0), (-1,-1), 8),
    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, DARK_GREY),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ('ROWBACKGROUNDS', (0,0), (-1,-1), [DARK_GREY, DARK_BG]),
]))
story.append(aud_table)

# ── 11. KPIs ───────────────────────────────────────────────────────────────
story.append(Paragraph("11. KPIs & Growth Targets", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Our 12-month KPIs reflect the foundations a healthy Web3 game needs to survive and scale. "
    "These targets are not a ceiling — they are the base from which Stage 5 ecosystem growth is launched.",
    body_style))

kpis = [
    ["Metric", "12-Month Target", "Why It Matters"],
    ["Registered Players", "1,000+", "Validates sign-up funnel and proves 1 SOL fee is not a barrier"],
    ["Daily Active Users", "300+", "30%+ DAU ratio signals strong retention and a sticky game loop"],
    ["$STR Market Cap", "$500K–$1M", "Indicates genuine token demand and economic confidence in the platform"],
    ["Marketplace Volume", "2,000+ SOL", "Directly drives 1% fee revenue; at $150/SOL = $300K+ in trade volume"],
    ["Discord Members", "3,000+", "Community size is a leading indicator for all other growth metrics"],
]
kpi_table = Table(kpis, colWidths=[1.9*inch, 1.5*inch, 3.0*inch])
kpi_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), PURPLE),
    ('TEXTCOLOR', (0,0), (-1,0), WHITE),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 9),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [DARK_GREY, DARK_BG]),
    ('TEXTCOLOR', (0,1), (-1,-1), GREY),
    ('TEXTCOLOR', (1,1), (1,-1), LIGHT_PURPLE),
    ('FONTNAME', (1,1), (1,-1), 'Helvetica-Bold'),
    ('TOPPADDING', (0,0), (-1,-1), 7),
    ('BOTTOMPADDING', (0,0), (-1,-1), 7),
    ('LEFTPADDING', (0,0), (-1,-1), 8),
    ('GRID', (0,0), (-1,-1), 0.5, DARK_GREY),
    ('VALIGN', (0,0), (-1,-1), 'TOP'),
]))
story.append(kpi_table)
story.append(PageBreak())

# ── 12. TEAM ───────────────────────────────────────────────────────────────
story.append(Paragraph("12. Team", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "Orbi is built by a small, focused team of developers and designers with backgrounds in mobile gaming, blockchain development, "
    "and crypto community building. The team is responsible for all aspects of the project — smart contract development in Rust using the Anchor framework, "
    "Python-powered backend and API layer, frontend UI, and community management across X and Discord. "
    "The 15% team allocation vests over the project lifecycle, aligning long-term incentives with player and investor success.",
    body_style))

# ── 13. LEGAL ──────────────────────────────────────────────────────────────
story.append(Paragraph("13. Legal Disclaimer", h1_style))
story.append(HRFlowable(width="100%", thickness=0.5, color=PURPLE))
story.append(Spacer(1, 0.1*inch))
story.append(Paragraph(
    "This whitepaper is for informational purposes only and does not constitute financial, investment, or legal advice. "
    "$STR tokens are utility tokens intended for use within the Orbi game ecosystem. "
    "Participation in the Orbi ecosystem involves risk, including the potential loss of funds. "
    "Nothing in this document should be construed as a guarantee of returns or future performance. "
    "Prospective participants should conduct their own due diligence and consult appropriate professional advisors before making any decisions. "
    "The Orbi team reserves the right to update or amend this whitepaper as the project evolves.",
    body_style))

story.append(Spacer(1, 0.3*inch))
story.append(HRFlowable(width="100%", thickness=0.5, color=DARK_GREY))
story.append(Spacer(1, 0.15*inch))
story.append(Paragraph("orbiapp123.github.io  |  @Orbi_solana  |  discord.gg/JGgGFaPK", small_grey))
story.append(Paragraph("Orbi: To the Moon — Whitepaper v1.0 — April 2026", small_grey))

doc.build(story, onFirstPage=bg_canvas, onLaterPages=bg_canvas)
print("Done")
