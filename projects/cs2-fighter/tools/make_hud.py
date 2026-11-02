"""Writes the custom_hud_layout files: panorama/layout/custom_game/puppet_brawl.xml + styles css.
Panel ids/classes here must match what scripts/puppet_brawl.js sets."""
import os, sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "dist/addon"

def card(n, side):
    return f"""			<Panel id="pb_c{n}" class="Card {side}" hittest="false">
				<Panel class="CardBody" hittest="false">
					<Panel class="CardTop" hittest="false">
						<Label id="pb_c{n}_name" class="CardName" text="{{s:t}}" />
						<Label id="pb_c{n}_fighter" class="CardFighter" text="{{s:t}}" />
						<Label class="YouTag" text="YOU" />
						<Label id="pb_c{n}_combo" class="ComboText" text="{{s:t}}" />
					</Panel>
					<Panel class="Bar" hittest="false">
						<Panel id="pb_c{n}_chip" class="Chip w100" hittest="false" />
						<Panel id="pb_c{n}_fill" class="Fill w100" hittest="false" />
						<Panel class="Shine" hittest="false" />
						<Panel class="Ticks" hittest="false">{TICKS}</Panel>
					</Panel>
					<Panel class="Pips" hittest="false">
						<Panel id="pb_c{n}_pip1" class="Pip" hittest="false" />
						<Panel id="pb_c{n}_pip2" class="Pip" hittest="false" />
						<Panel id="pb_c{n}_pip3" class="Pip Pip3" hittest="false" />
						<Label id="pb_c{n}_best" class="BestText" text="{{s:t}}" />
					</Panel>
				</Panel>
				<Panel class="Stripe" hittest="false" />
				<Panel class="Notch" hittest="false" />
			</Panel>"""

TICKS = "".join('<Panel class="Tick" hittest="false" />' for _ in range(10))

XML = f"""<root>
	<styles>
		<include src="file://{{resources}}/styles/custom_game/puppet_brawl.css" />
	</styles>

	<Panel class="PBRoot" hittest="false">
		<Panel id="pb_joinhint" class="JoinHint" hittest="false">
			<Label id="pb_joinhint_text" class="JoinHintText" text="{{s:t}}" />
		</Panel>

		<Panel id="pb_game" class="Game Hidden" hittest="false">
{card(1, "Left")}
{card(2, "Right")}
{card(3, "Left Row2")}
{card(4, "Right Row2")}
			<Panel class="CenterTop" hittest="false">
				<Panel class="TimerPlate" hittest="false">
					<Label id="pb_timer" class="Timer" text="{{s:t}}" />
				</Panel>
				<Label id="pb_queue" class="Queue" text="{{s:t}}" />
			</Panel>

			<Label id="pb_announce" class="Announce" text="{{s:t}}" />

			<Panel id="pb_lobby" class="Lobby" hittest="false">
				<Panel class="Hazard" hittest="false" />
				<Label class="LobbyTitle" text="PUPPET BRAWL" />
				<Label class="LobbyTag" text="NIGHT MARKET  //  NO RULES  //  NO STRINGS ATTACHED" />
				<Label id="pb_lobby_mode" class="LobbyMode" text="{{s:t}}" />
				<Label id="pb_lobby_s1" class="LobbyRow" text="{{s:t}}" />
				<Label id="pb_lobby_s2" class="LobbyRow" text="{{s:t}}" />
				<Label id="pb_lobby_s3" class="LobbyRow" text="{{s:t}}" />
				<Label id="pb_lobby_s4" class="LobbyRow" text="{{s:t}}" />
				<Label id="pb_lobby_count" class="LobbyCount" text="{{s:t}}" />
				<Label id="pb_lobby_hint" class="LobbyHint" text="{{s:t}}" />
			</Panel>

			<Panel class="MeBox" hittest="false">
				<Panel class="Hazard Thin" hittest="false" />
				<Label id="pb_me" class="MeLine" text="{{s:t}}" />
				<Label id="pb_moves" class="MeMoves" text="{{s:t}}" />
				<Label id="pb_motions" class="MeMotions" text="{{s:t}}" />
				<Label id="pb_status" class="MeStatus" text="{{s:t}}" />
			</Panel>

			<Label id="pb_footer" class="Footer" text="{{s:t}}" />
		</Panel>
	</Panel>
</root>
"""

COLORS = ["#d8281e", "#2c7ad8", "#4aa83c", "#e2a81a", "#e2621a", "#22a8b4"]

CSS = """/* Puppet Brawl HUD - driven by scripts/puppet_brawl.js through custom_hud_layout pb_hud.
   Look: back-alley arcade. Hard edges, scuffed charcoal plates, heavy black outlines,
   blood-to-fire health bars and an amber-framed clock. */

.PBRoot { width: 100%; height: 100%; font-family: Stratum2; }

.Game {
	width: 100%; height: 100%;
	opacity: 1;
	transition-property: opacity; transition-duration: 0.25s;
}
.Game.Hidden { opacity: 0; }

@keyframes 'pb-throb' { 0% { opacity: 1; } 50% { opacity: 0.55; } 100% { opacity: 1; } }

/* ---------------------------------------------------------------- player cards */
.Card {
	width: 610px; height: 96px;
	vertical-align: top;
	margin-top: 22px;
	opacity: 0;
	transition-property: opacity; transition-duration: 0.2s;
}
.Card.Left { horizontal-align: left; margin-left: 30px; }
.Card.Right { horizontal-align: right; margin-right: 30px; }
.Card.Row2 { margin-top: 128px; height: 86px; }
.Card.Show { opacity: 1; }
.Card.Show.KO { opacity: 0.4; }

.CardBody {
	width: 100%; height: 100%;
	padding: 8px 18px 0px 26px;
	flow-children: down;
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #262321f2 ), color-stop( 0.5, #141312f2 ), to( #070707f2 ) );
	border: 3px solid #000000;
	border-top: 3px solid #3a3530;
	box-shadow: #000000cc 4px 5px 0px 0px;
}
.Card.Right .CardBody { padding: 8px 26px 0px 18px; }
.Card.Me .CardBody { border: 3px solid #e2a81a; }

/* team / seat colour: a thick bar down the outside edge, with a cut notch at its top */
.Stripe { width: 9px; height: 100%; horizontal-align: left; background-color: #ffffff; border-right: 3px solid #000000; }
.Card.Right .Stripe { horizontal-align: right; border-right: 0px solid #000000; border-left: 3px solid #000000; }
.Notch { width: 26px; height: 8px; horizontal-align: left; vertical-align: top; background-color: #ffffff; margin-left: 9px; }
.Card.Right .Notch { horizontal-align: right; margin-left: 0px; margin-right: 9px; }

.CardTop { width: 100%; height: 30px; flow-children: right; }
.Card.Right .CardTop { flow-children: left; }
.CardName {
	font-size: 25px; font-weight: black; color: #ffffff;
	text-transform: uppercase; letter-spacing: 2px;
	text-shadow: 2px 2px 0px 1.0 #000000;
}
.CardFighter {
	font-size: 16px; font-weight: bold; color: #1a1714;
	background-color: #b8ad98; padding: 2px 8px 0px 8px;
	margin: 4px 12px 0px 12px; letter-spacing: 3px; text-transform: uppercase;
	border: 1px solid #000000;
}
.YouTag {
	font-size: 15px; font-weight: black; color: #0c0a06;
	background-color: #e2a81a; padding: 2px 7px 0px 7px; margin-top: 4px;
	border: 1px solid #000000; letter-spacing: 2px;
	visibility: collapse;
}
.Card.Me .YouTag { visibility: visible; }
.ComboText {
	font-size: 22px; font-weight: black; color: #ff8a1e;
	margin: 1px 12px 0px 12px; letter-spacing: 1px; text-transform: uppercase;
	text-shadow: 3px 3px 0px 1.0 #000000;
	opacity: 0;
	transition-property: opacity; transition-duration: 0.1s;
}
.Card.HasCombo .ComboText { opacity: 1; }
.Card.Perfect .ComboText { color: #a8f6ff; text-shadow: 3px 3px 0px 1.0 #00303a; }
.BestText {
	font-size: 15px; font-weight: bold; color: #c9b88e;
	margin: 0px 12px; vertical-align: center; letter-spacing: 2px; text-transform: uppercase;
	text-shadow: 1px 1px 0px 1.0 #000000;
	opacity: 0;
}
.Card.HasBest .BestText { opacity: 1; }
.Card.Bench { opacity: 0.5; }

/* health: blood-dark trough, white-hot damage chip, fire fill, segment ticks */
.Bar {
	width: 100%; height: 26px; margin-top: 4px;
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #2a0605 ), to( #120202 ) );
	border: 3px solid #000000;
}
.Fill, .Chip { height: 100%; horizontal-align: left; }
.Card.Right .Fill, .Card.Right .Chip { horizontal-align: right; }
.Chip { background-color: #fff0c8; transition-property: width; transition-duration: 0.55s; transition-delay: 0.35s; transition-timing-function: ease-out; }
.Fill {
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #ffc04a ), color-stop( 0.4, #f2601a ), to( #9a1208 ) );
	transition-property: width; transition-duration: 0.08s;
}
.Card.Low .Fill {
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #ff5a3a ), color-stop( 0.45, #c4160c ), to( #5a0402 ) );
	animation-name: pb-throb; animation-duration: 0.7s; animation-iteration-count: infinite;
}
.Shine { width: 100%; height: 30%; vertical-align: top; background-color: #ffffff1c; }
.Ticks { width: 100%; height: 100%; flow-children: right; }
.Tick { width: 10%; height: 100%; border-right: 2px solid #00000080; }
.Card.Row2 .Bar { height: 18px; }

/* round wins: hard diamonds */
.Pips { flow-children: right; margin-top: 7px; margin-left: 2px; }
.Card.Right .Pips { horizontal-align: right; flow-children: left; margin-left: 0px; margin-right: 2px; }
.Pip {
	width: 13px; height: 13px; margin: 0px 6px;
	background-color: #2a2622; border: 2px solid #000000;
	transform: rotateZ( 45deg );
}
.Pip.Won { background-color: #ff6a1e; border: 2px solid #ffd27a; box-shadow: #ff3a0a99 0px 0px 6px 1px; }
.Pip3 { visibility: collapse; }
.Card.Need3 .Pip3 { visibility: visible; }

/* ---------------------------------------------------------------- centre top: the clock */
.CenterTop { horizontal-align: center; vertical-align: top; margin-top: 14px; flow-children: down; width: 360px; }
.TimerPlate {
	horizontal-align: center;
	flow-children: down; min-width: 132px; padding: 0px 14px;
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #1d1b19f4 ), to( #050505f4 ) );
	border: 4px solid #000000;
	box-shadow: #e2a81aaa 0px 0px 0px 3px;
}
.Timer {
	horizontal-align: center;
	font-size: 76px; font-weight: black; color: #f4e2b8;
	text-shadow: 3px 3px 0px 1.0 #000000;
}
.Timer.Low { color: #ff4a2a; animation-name: pb-throb; animation-duration: 0.5s; animation-iteration-count: infinite; }
.Queue {
	horizontal-align: center; margin-top: 10px;
	font-size: 18px; font-weight: bold; color: #d9cdb2; letter-spacing: 2px; text-transform: uppercase;
	text-shadow: 2px 2px 0px 1.0 #000000; text-align: center;
}

/* ---------------------------------------------------------------- announcer */
.Announce {
	horizontal-align: center; vertical-align: center;
	margin-bottom: 140px;
	font-size: 108px; font-weight: black; color: #f6ead0;
	text-align: center; letter-spacing: 6px; text-transform: uppercase;
	text-shadow: 7px 7px 0px 1.0 #000000;
	opacity: 0;
	pre-transform-scale2d: 1.6;
	transition-property: opacity, pre-transform-scale2d; transition-duration: 0.12s; transition-timing-function: ease-in;
}
.Announce.Show { opacity: 1; pre-transform-scale2d: 1; }
.Announce.St_fight { color: #ff7a1a; font-size: 140px; pre-transform-rotate2d: -4deg; }
.Announce.St_ko { color: #e01a10; font-size: 180px; letter-spacing: 14px; pre-transform-rotate2d: -6deg; text-shadow: 9px 9px 0px 1.0 #000000; }
.Announce.St_big { color: #f6ead0; }
.Announce.St_win { font-size: 84px; color: #ffcf5a; }
.Announce.St_sub { font-size: 44px; margin-bottom: -40px; color: #d9cdb2; letter-spacing: 4px; text-shadow: 4px 4px 0px 1.0 #000000; }
.Announce.St_small { font-size: 40px; margin-bottom: 40px; letter-spacing: 3px; text-shadow: 4px 4px 0px 1.0 #000000; }

/* ---------------------------------------------------------------- lobby: a steel plate */
.Lobby {
	horizontal-align: center; vertical-align: top;
	margin-top: 120px;
	width: 1000px;
	padding: 0px 34px 24px 34px;
	flow-children: down;
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #2a2b2df4 ), color-stop( 0.08, #1a1b1df4 ), to( #08090af4 ) );
	border: 4px solid #000000;
	box-shadow: #000000cc 6px 7px 0px 0px;
	opacity: 0;
	transition-property: opacity; transition-duration: 0.2s;
}
.Game.InLobby .Lobby { opacity: 1; }
.Hazard {
	width: 100%; height: 10px; margin-top: 14px; margin-bottom: 14px;
	background-color: gradient( linear, 0% 0%, 100% 0%, from( #e2a81a ), color-stop( 0.5, #c27a10 ), to( #e2a81a ) );
	border-bottom: 3px solid #000000;
}
.Hazard.Thin { width: 100%; height: 5px; margin-top: 8px; margin-bottom: 8px; border-bottom: 2px solid #000000; }
.LobbyTitle {
	horizontal-align: center; font-size: 58px; font-weight: black; color: #ff7a1a; letter-spacing: 10px;
	text-shadow: 5px 5px 0px 1.0 #000000;
}
.LobbyTag { horizontal-align: center; font-size: 15px; font-weight: bold; color: #8e8778; letter-spacing: 4px; margin-bottom: 8px; }
.LobbyMode {
	horizontal-align: center; font-size: 22px; font-weight: bold; color: #0c0a06; letter-spacing: 3px;
	background-color: #e2a81a; padding: 3px 14px 1px 14px; margin-bottom: 14px; border: 2px solid #000000;
}
.LobbyRow {
	width: 100%;
	font-size: 23px; color: #77716a; margin: 3px 0px; padding: 3px 10px;
	background-color: #00000066; border-left: 4px solid #2e2b28; text-transform: uppercase; letter-spacing: 1px;
}
.LobbyRow.Taken { color: #efe6d2; border-left: 4px solid #8e8778; }
.LobbyRow.Ready { color: #9cf07a; border-left: 4px solid #4aa83c; }
.LobbyRow.Me { font-weight: black; }
.LobbyCount { horizontal-align: center; font-size: 26px; font-weight: black; color: #ff8a1e; margin-top: 16px; letter-spacing: 2px; text-shadow: 3px 3px 0px 1.0 #000000; }
.LobbyHint { horizontal-align: center; font-size: 18px; color: #a59d8d; margin-top: 6px; letter-spacing: 1px; }

/* ---------------------------------------------------------------- your fighter */
.MeBox {
	horizontal-align: center; vertical-align: bottom;
	margin-bottom: 54px;
	width: 1300px;
	flow-children: down;
	padding: 0px 20px 10px 20px;
	background-color: gradient( linear, 0% 0%, 0% 100%, from( #1d1c1bee ), to( #060606ee ) );
	border: 3px solid #000000;
	box-shadow: #000000cc 5px 6px 0px 0px;
	opacity: 0;
	transition-property: opacity; transition-duration: 0.2s;
}
.Game.InLobby .MeBox, .Game.Picking .MeBox { opacity: 1; }
.MeLine { horizontal-align: center; font-size: 22px; color: #ffffff; font-weight: black; text-align: center; letter-spacing: 2px; text-transform: uppercase; }
.MeMoves { horizontal-align: center; font-size: 19px; color: #ddd3bd; text-align: center; margin-top: 4px; }
.MeMotions { horizontal-align: center; font-size: 16px; color: #958d7e; text-align: center; }
.MeStatus { horizontal-align: center; font-size: 22px; color: #ff8a1e; font-weight: black; margin-top: 4px; letter-spacing: 2px; text-transform: uppercase; }

.Footer {
	horizontal-align: center; vertical-align: bottom;
	margin-bottom: 14px;
	font-size: 17px; font-weight: bold; color: #d9cdb2b0; letter-spacing: 2px;
	text-shadow: 2px 2px 0px 1.0 #000000;
}

/* ---------------------------------------------------------------- join prompt */
.JoinHint {
	horizontal-align: center; vertical-align: bottom;
	margin-bottom: 260px;
	padding: 10px 26px 8px 26px;
	background-color: #070707ee;
	border: 3px solid #e2a81a;
	box-shadow: #000000cc 5px 6px 0px 0px;
	opacity: 0;
	transition-property: opacity; transition-duration: 0.15s;
}
.JoinHint.Show { opacity: 1; }
.JoinHintText { font-size: 28px; font-weight: black; color: #ffcf5a; letter-spacing: 3px; text-shadow: 2px 2px 0px 1.0 #000000; }
"""

def main():
    lay = os.path.join(OUT, "panorama", "layout", "custom_game"); os.makedirs(lay, exist_ok=True)
    sty = os.path.join(OUT, "panorama", "styles", "custom_game"); os.makedirs(sty, exist_ok=True)
    with open(os.path.join(lay, "puppet_brawl.xml"), "w", newline="\n") as f: f.write(XML)
    css = CSS
    css += "\n/* card colours (Col0-3 seats, Col4-5 second team colours) */\n"
    for i, c in enumerate(COLORS):
        css += f".Card.Col{i} .Stripe, .Card.Col{i} .Notch {{ background-color: {c}; }}\n.Card.Col{i} .CardName {{ color: {c}; }}\n"
    css += "\n/* health widths set by the script */\n"
    for w in range(101):
        css += f".w{w} {{ width: {w}%; }}\n"
    with open(os.path.join(sty, "puppet_brawl.css"), "w", newline="\n") as f: f.write(css)
    print("hud written")

if __name__ == "__main__":
    main()
