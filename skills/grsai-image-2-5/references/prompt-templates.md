# grsai Prompt Templates

All templates use the same labelled-block skeleton:

`ROLE OF THE REFERENCES` → `CAMERA` → `MATERIALS AND TEXTURE` (real mm, micro-relief)
→ `JOINT AND DIVISION LINES` → `GROUND AND PLANTING` → `LIGHT AND RENDER` → `LOOK / NEGATIVES`

Keep the geometry-lock paragraph **verbatim** when re-skinning a 3D model view: it is the
part that stops the model from inventing storeys or windows.

---

## Geometry lock paragraph (reuse verbatim)

```
ROLE OF THE REFERENCES - image 1 is the exact required CAMERA, FRAMING and STRUCTURE of the
building; image 2 is the same structure as a pure white massing study. The building form is
LOCKED: <N> stacked storeys with identical floor-to-floor heights, identical footprint, the
identical count, positions, widths, sill heights and head heights of every window and door
opening, the same recessed balcony bays, the same flat roof slab and its upstand parapet, the
same side carport canopy, and the same plinth band. Never add, remove, merge, split, resize or
relocate any storey, opening, balcony, roof, canopy or railing. Only materials, textures,
joints, lighting and landscape may change - the target is to re-skin this exact building in
the style of the reference photograph.
```

## Camera block

```
CAMERA - identical to image 1: eye height <H> m, standing <position>, looking slightly upward,
50 mm full-frame lens, tilt-shift perspective correction so every vertical line stays perfectly
vertical, identical crop, identical sky proportion and identical amount of foreground.
```

---

## 1. Premium contemporary Western residence

```
MATERIALS AND TEXTURE (real-world scale, visible micro-relief) -
Walls: 2 mm mineral through-coloured lime-cement render, warm off-white, hand-troweled with faint
spatula sweeps, fine sand grain that catches the raking light, matte with a very slight chalky
sheen, clouded tonal variation from weathering, one or two hairline shrinkage cracks.
Base: 40 mm split-face natural limestone veneer, dry-stacked coursing of mixed 60-160 mm heights,
honed-sawn faces, 8 mm recessed flush joints, occasional open joint for depth, anchored by a
20 mm chamfered cast-stone plinth cap.
Windows: slim 45 mm matte-black anodized aluminium frames, deep shadow reveal, flush dark-stone
rebate sill with a 12 mm drip groove, 6 mm low-iron glass, faint green edge tint, physically
correct sky and street reflection, gentle double reflection between panes, faint dust and
micro-smudge on the lower panes.
Front door: solid quarter-sawn white oak, warm oiled walnut tone, 6 mm deep grain, visible
cathedral figure, brushed-unlacquered brass handleset and kick plate with faint patina.
Garage door: warm grey polyurethane-coated steel, sectional carriage panels with crisp shadow
grooves, micro-peen orange-peel paint, black wrought-iron strap hinges with hammer marks.
Metal: dark bronze-anodized standing-seam fascia, hairline brushed anisotropy; 100 mm light-grey
powder-coated aluminium downpipe with cast shoe and clean brackets.
Paving: 900 x 300 x 60 mm dark grey granite, sawn surface, 3 mm sand joints, flamed border
courses, wet sheen from a recent wash; honed concrete walkway with 6 mm saw-cut control joints.
```

## 2. Tuscan / Mediterranean countryside villa

```
Walls: warm lime-cream lime-and-sand stucco, off-white with soft pink-beige warmth, 3 mm coat,
hand-troweled with gentle sweeps and slight undulation, fine sand grain, sun-bleached clouding.
Eaves: deep traditional Roman terracotta pantile overhang, 300 mm projection, 40 mm barrel tiles,
mixed hand-laid cream/ochre/terracotta with moss in the shadow valleys, smooth 120 mm tile course
at the fascia, white painted soffit with exposed rafter tails.
Windows: chestnut-brown stained oak frames, 70 mm, slender 20 mm muntins forming a 6 x 8 grid of
small lights, 30 mm deep white stone surrounds with projecting cap and drip.
Balcony: black wrought-iron railing, 12 mm square balusters at 110 mm centres, 40 mm flat
handrail with scroll returns, satin black powder coat with tiny chips showing bare steel;
terracotta pot with clipped boxwood ball and trailing geranium.
Garden: gently curving 600 x 400 mm honed sandstone stepping slabs set in fine gravel, terracotta
pots of olive, myrtle and boxwood, massed lavender, rosemary, santolina, white and blush roses,
catmint and ornamental grasses, low clipped boxwood border, two slim bollard lights.
```

## 3. Neo-Classic / European-American villa

```
Walls: light warm greige-beige lime stucco, 3 mm coat, hand-troweled, fine sand grain, matte,
faint cloudy weathering, 12 mm shadow reveals at every external corner, 400 mm pilaster strips at
the ground-floor corners.
Mouldings: deep two-step crown cornice with cyma recta profile projecting 200 mm at the top and
above every opening, projecting water table 80 mm at the base, banded string course at each floor
with a 25 mm drip, all in the same stucco, each casting a soft self-shadow.
Windows: 70 mm white-painted timber frames with a 1:2 arch head, 150 mm projecting architrave with
keystone, louvered white plantation shutters at 45 mm slats / 30 degree pitch folded flat into the
reveal, 30 mm white stone sill with drip groove.
Entrance: solid white oak door, oiled natural tone, brushed-unlacquered brass lever and knocker,
flanked by two black rectangular wall lanterns with warm glass on visible bracket arms.
Forecourt: light beige honed limestone pavers 600 x 600 mm with crisp 4 mm joints, white pea gravel
bed with a black painted slat garden bench, black wrought-iron spear-finial gate, clipped boxwood,
tropical broadleaf shrubs, slender palm trunk.
```

## 4. Product / cut-out (transparent background)

```
A single <object> photographed straight on, centred, floating on a seamless white sweep, soft
large-source key light from the upper left, subtle fill card on the right, gentle contact shadow
falling to the lower right, crisp specular highlight along the <material> edge, visible micro
texture and faint dust, no props, no text, no watermark, cut-out ready with clean edges.
```
Use with `--model gpt-image-2.5-flare --background transparent --quality high --aspect 1024x1024`.

---

## Joint / division line block (copy-paste, adapt the numbers)

```
JOINT AND DIVISION LINES - crisp 12 mm shadow-gap reveals around every window and door and at
every external corner; a continuous 20 mm recessed shadow line under the cornice, under every
moulding, sill, ledge, coping and balcony slab so each element reads as its own plane; each floor
slab edge expressed as a 12 mm recessed horizontal shadow line with a crisp aluminium drip edge;
8 mm raked control joints on the large wall fields aligned to the cladding module; mullions,
transoms, shutter slats, stone coursing, architrave mitres and paving joints all resolving on one
module so nothing is left half-cut or misaligned; no soft or smeared edges anywhere.
```

## Light / render block (copy-paste)

```
LIGHT AND RENDER - warm late-afternoon sun raking in from the left front at a low grazing angle so
the render grain, stone relief and joint depths are all readable; cool sky bounce filling the
window reveals and recesses; warm bounce off the paving back onto the wainscot; long crisp cast
shadows; soft ambient occlusion in every junction; clean highlight roll-off; subtle lens vignette.
Photographed on a full-frame 50 mm at f/8, ISO 100, deep focus with natural falloff, neutral white
balance, high dynamic range, extremely high micro-detail, restrained film grain, magazine-grade
architectural photography, no people, no cars, no signage, no text, no watermark, no distortion,
no fisheye.
```

## Material / finish word bank

- **Stucco/render**: through-coloured, lime-cement, lime-and-sand, hand-troweled, spatula sweeps, fine sand grain, chalky sheen, clouded tonal variation, sun-bleached, hairline shrinkage crack, slight undulation.
- **Stone**: split-face, honed, sawn, flamed, dry-stacked, mixed coursing, recessed flush joints, open joint, vein figure, chamfered cap, drip groove, water table.
- **Metal**: anodized, hairline brushed anisotropy, powder-coated, standing-seam, micro-peen orange peel, hand-forged hammer marks, satin black with chips to bare steel, unlacquered brass with fingerprint patina.
- **Timber**: quarter-sawn, cathedral figure, 6 mm grain, oiled, stained, raised panel, exposed rafter tail, soffit.
- **Glass**: low-iron, faint green edge tint, double reflection between panes, interior depth, dust on lower panes, micro-smudge.
- **Concrete/granite**: sawn, flamed, honed, saw-cut control joints, sand joints, wet sheen, exposed aggregate.
- **Quality cues**: aligned module, shadow gap, expressed reveal, drip edge, shadow line, crisp mitre, tight tolerance, no half-cut piece.
