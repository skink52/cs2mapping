"""mg_trenchwarfare HUD (custom_hud_layout): panorama/layout/custom_game/mg_trenchwarfare.xml + css + pictures.
Ids and classes must match maps/scripts/mg_trenchwarfare.js. Text goes through dialog variables ({s:v})."""
import os, sys, json
import numpy as np
from PIL import Image, ImageDraw
import tw_cockpit

OUT = sys.argv[1] if len(sys.argv) > 1 else '../out/addon'
NAME = 'mg_trenchwarfare'
IMG = 'file://{images}/custom_game/tw/'
IMGDIR = os.path.join(OUT, 'panorama/images/custom_game/tw'); os.makedirs(IMGDIR, exist_ok=True)
TM = 768             # targeting map size (px)
STEPS = 192          # crosshair positions per axis
FONT = 'Stratum2, "Stratum2 Bold", Arial'
css = []
def rule(sel, **p):
    css.append('%s {\n%s}\n' % (sel, ''.join('\t%s: %s;\n' % (k.replace('_', '-'), v) for k, v in p.items())))

# ---------------------------------------------------------------- pictures
def reticle(size=96):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = size // 2
    g = (140, 255, 170, 255)
    d.ellipse((c - 30, c - 30, c + 30, c + 30), outline=g, width=3)
    d.ellipse((c - 3, c - 3, c + 3, c + 3), fill=g)
    for a, b in (((c, 4), (c, c - 14)), ((c, c + 14), (c, size - 4)), ((4, c), (c - 14, c)), ((c + 14, c), (size - 4, c))):
        d.line([a, b], fill=g, width=3)
    return im
def diamond(size=48, col=(255, 80, 60, 255)):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im); c = size // 2
    d.polygon([(c, 3), (size - 3, c), (c, size - 3), (3, c)], outline=col, width=4)
    d.line([(c - 6, c), (c + 6, c)], fill=col, width=2); d.line([(c, c - 6), (c, c + 6)], fill=col, width=2)
    return im
def cross(size=32, col=(255, 170, 60, 255)):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.line([(4, 4), (size - 4, size - 4)], fill=col, width=4); d.line([(size - 4, 4), (4, size - 4)], fill=col, width=4)
    return im
def square(size=24, col=(90, 170, 255, 255)):
    im = Image.new('RGBA', (size, size), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rectangle((3, 3, size - 4, size - 4), outline=col, width=3); d.rectangle((9, 9, size - 10, size - 10), fill=col)
    return im
def scan(size=8):
    a = np.zeros((size, size, 4), np.uint8); a[::2, :, 3] = 60
    return Image.fromarray(a)
def paper(w=512, h=160):
    rng = np.random.RandomState(3)
    a = np.zeros((h, w, 4), np.float32)
    a[..., 0] = 0.12; a[..., 1] = 0.11; a[..., 2] = 0.09; a[..., 3] = 0.82
    n = rng.normal(0, 0.02, (h, w)); a[..., :3] += n[..., None]
    a[:3, :, :3] = (0.62, 0.52, 0.32); a[-3:, :, :3] = (0.62, 0.52, 0.32); a[:, :3, :3] = (0.62, 0.52, 0.32); a[:, -3:, :3] = (0.62, 0.52, 0.32)
    a[:3, :, 3] = a[-3:, :, 3] = a[:, :3, 3] = a[:, -3:, 3] = 1
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
reticle().save(os.path.join(IMGDIR, 'reticle.png')); diamond().save(os.path.join(IMGDIR, 'locked.png'))
cross().save(os.path.join(IMGDIR, 'impact.png')); square().save(os.path.join(IMGDIR, 'pit.png'))
scan().save(os.path.join(IMGDIR, 'scan.png')); paper().save(os.path.join(IMGDIR, 'panel.png'))
tw_cockpit.build(IMGDIR)

# ---------------------------------------------------------------- css
rule('.TWRoot', width='100%', height='100%')
rule('.TWRoot Label', font_family=FONT, color='#e8dcc0', text_shadow='2px 2px 0px #000000', font_weight='bold')
rule('.Hide', opacity='0')
rule('.Box', background_image='url("%spanel.png")' % IMG, background_size='100% 100%', padding='14px 20px 14px 20px', flow_children='down')
# role banner (top centre, under CS2's team counter)
rule('#tw_banner', horizontal_align='center', margin_top='96px', width='980px', opacity='0', transition_property='opacity', transition_duration='0.4s')
rule('#tw_banner.show', opacity='1')
rule('#tw_banner_title', font_size='46px', color='#f0d48a', horizontal_align='center', letter_spacing='3px')
rule('#tw_banner_sub', font_size='24px', horizontal_align='center', margin_top='4px')
# lobby orders (centre)
rule('#tw_brief', horizontal_align='center', vertical_align='center', width='860px', opacity='0', transition_property='opacity', transition_duration='0.3s')
rule('#tw_brief.show', opacity='1')
rule('#tw_brief_title', font_size='30px', color='#c9a24e', horizontal_align='center', letter_spacing='6px')
rule('#tw_brief_role', font_size='54px', color='#f0d48a', horizontal_align='center', margin_top='6px')
rule('.BriefLine', font_size='24px', horizontal_align='center', margin_top='6px')
rule('#tw_brief_count', font_size='26px', color='#a8d0a0', horizontal_align='center', margin_top='14px')
# status (left, below the radar)
rule('#tw_status', margin_left='24px', margin_top='330px', width='360px', opacity='0', transition_property='opacity', transition_duration='0.3s')
rule('#tw_status.show', opacity='1')
rule('#tw_st_role', font_size='26px', color='#f0d48a')
rule('.StLine', font_size='20px', margin_top='4px')
# prompt (bottom centre, above CS2's health / ammo row)
rule('#tw_prompt', horizontal_align='center', vertical_align='bottom', margin_bottom='170px', opacity='0', transition_property='opacity', transition_duration='0.15s')
rule('#tw_prompt.show', opacity='1')
rule('#tw_prompt_text', font_size='28px', color='#ffffff', horizontal_align='center')
# toast (upper centre)
rule('#tw_toast', horizontal_align='center', margin_top='300px', opacity='0', transition_property='opacity', transition_duration='0.25s')
rule('#tw_toast.show', opacity='1')
rule('#tw_toast_text', font_size='36px', color='#ffcf6a', horizontal_align='center')
# role orders card (right of centre; chat !infantry / !mortar / !air / !roles)
rule('#tw_info', horizontal_align='right', vertical_align='center', margin_right='60px', width='560px', opacity='0', transition_property='opacity', transition_duration='0.3s')
rule('#tw_info.show', opacity='1')
rule('#tw_info_title', font_size='34px', color='#f0d48a', letter_spacing='3px')
rule('.InfoLine', font_size='22px', margin_top='7px')
rule('#tw_info_foot', font_size='18px', color='#a8d0a0', margin_top='12px')
# targeting screen
rule('#tw_target', horizontal_align='center', vertical_align='center', width='%dpx' % (TM + 340), height='%dpx' % (TM + 40), opacity='0',
     transition_property='opacity', transition_duration='0.2s', background_color='#05110bdd', border='3px solid #3c8a5a')
rule('#tw_target.show', opacity='1')
rule('#tw_tmap', margin_left='20px', margin_top='20px', width='%dpx' % TM, height='%dpx' % TM, background_size='100% 100%', overflow='noclip')
rule('#tw_tmap.mt', background_image='url("%starget_t.png")' % IMG)
rule('#tw_tmap.mct', background_image='url("%starget_ct.png")' % IMG)
rule('.Scan', width='100%', height='100%', background_image='url("%sscan.png")' % IMG, background_size='8px 8px', background_repeat='repeat')
markers = [('Ret', 96, 'reticle.png'), ('Lock', 48, 'locked.png'), ('Imp', 32, 'impact.png'), ('Pit', 24, 'pit.png')]
for cls, sz, png in markers:
    rule('.%sCol' % cls, width='%dpx' % sz, height='%dpx' % TM, overflow='noclip', opacity='0')
    rule('.%sCol.on' % cls, opacity='1')
    rule('.%sSq' % cls, width='%dpx' % sz, height='%dpx' % sz, background_image='url("%s%s")' % (IMG, png), background_size='100% 100%')
    for i in range(STEPS):
        c = (i + 0.5) * TM / STEPS
        rule('.%sCol.x%d' % (cls, i), transform='translatex(%dpx)' % int(round(c - sz / 2)))
        rule('.%sSq.y%d' % (cls, i), transform='translatey(%dpx)' % int(round(c - sz / 2)))
rule('#tw_tside', margin_left='%dpx' % (TM + 40), margin_top='24px', width='290px', flow_children='down')
rule('#tw_t_title', font_size='28px', color='#8cffaa', letter_spacing='3px')
rule('.TLine', font_size='20px', color='#b8f0c8', margin_top='8px')
rule('.THelp', font_size='17px', color='#88b898', margin_top='5px')
rule('#tw_t_state', font_size='24px', color='#ffd070', margin_top='18px')

# ---------------------------------------------------------------- layout
def lab(id_, cls=''):
    return '<Label id="%s" class="%s" text="{s:v}" />' % (id_, cls)
FLY = tw_cockpit.css_xml(rule, IMG, lab)
def marker(prefix, cls):
    return '<Panel id="%s" class="%sCol" hittest="false"><Panel id="%sy" class="%sSq" hittest="false" /></Panel>' % (prefix, cls, prefix, cls)
imp = ''.join(marker('tw_imp%d' % k, 'Imp') for k in range(3))
xml = '''<root>
	<styles>
		<include src="file://{resources}/styles/custom_game/%s.css" />
	</styles>
	<Panel class="TWRoot" hittest="false">
		%s
		<Panel id="tw_banner" class="Box" hittest="false">%s%s</Panel>
		<Panel id="tw_brief" class="Box" hittest="false">
			<Label id="tw_brief_title" text="ORDERS" />%s%s%s%s%s
		</Panel>
		<Panel id="tw_status" class="Box" hittest="false">%s%s%s%s</Panel>
		<Panel id="tw_toast" class="Box" hittest="false">%s</Panel>
		<Panel id="tw_info" class="Box" hittest="false">%s</Panel>
		<Panel id="tw_prompt" class="Box" hittest="false">%s</Panel>
		<Panel id="tw_target" hittest="false">
			<Panel id="tw_tmap" hittest="false">
				<Panel class="Scan" hittest="false" />
				%s%s%s%s
			</Panel>
			<Panel id="tw_tside" hittest="false">
				<Label id="tw_t_title" text="MORTAR SIGHT" />
				%s%s%s%s
				<Label class="THelp" text="W A S D  move the sight" />
				<Label class="THelp" text="WALK (shift)  fine adjust" />
				<Label class="THelp" text="MOUSE 1  lock the target" />
				<Label class="THelp" text="JUMP  fire (when loaded)" />
				<Label class="THelp" text="USE (E)  leave the table" />
			</Panel>
		</Panel>
	</Panel>
</root>
''' % (NAME, FLY, lab('tw_banner_title'), lab('tw_banner_sub'),
       lab('tw_brief_role'), lab('tw_brief_l1', 'BriefLine'), lab('tw_brief_l2', 'BriefLine'), lab('tw_brief_l3', 'BriefLine'), lab('tw_brief_count'),
       lab('tw_st_role'), lab('tw_st_l1', 'StLine'), lab('tw_st_l2', 'StLine'), lab('tw_st_l3', 'StLine'),
       lab('tw_toast_text'), lab('tw_info_title') + ''.join(lab('tw_info_l%d' % k, 'InfoLine') for k in range(1, 6)) + lab('tw_info_foot'), lab('tw_prompt_text'),
       marker('tw_pit', 'Pit'), imp, marker('tw_lock', 'Lock'), marker('tw_ret', 'Ret'),
       lab('tw_t_range', 'TLine'), lab('tw_t_grid', 'TLine'), lab('tw_t_tube', 'TLine'), lab('tw_t_state'))
os.makedirs(os.path.join(OUT, 'panorama/layout/custom_game'), exist_ok=True)
os.makedirs(os.path.join(OUT, 'panorama/styles/custom_game'), exist_ok=True)
open(os.path.join(OUT, 'panorama/layout/custom_game/%s.xml' % NAME), 'w', newline='\n').write(xml)
open(os.path.join(OUT, 'panorama/styles/custom_game/%s.css' % NAME), 'w', newline='\n').write('\n'.join(css))
json.dump(dict(tm=TM, steps=STEPS), open(os.path.join(os.path.dirname(__file__), '..', 'out', 'hud.json'), 'w'))
print('hud: %d css rules' % len(css))
