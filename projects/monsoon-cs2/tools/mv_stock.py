"""Stock CS2 models used by mg_monsoon's places, with their bounds, and fallback bounds for our own props that are not built yet.

STOCK: (lo, hi) in model units, MEASURED from the compiled models in pak01 with create/s2/bounds_batch.mjs (11 Nov 2026).
FALLBACK: conservative estimates for models/mv props; out/props.json (written by build_all_props.py) wins whenever it has the prop.
TRUNK: collision radius of tree trunks (their canopies overlap freely); used for the placer footprints of trees.
The bicycle (models/vehicles/bicycle_01) is a kit of loose parts (frame, wheels, handlebar) with no assembled model: not used.
"""
import os, json

AZ = 'models/props/de_aztec/hr_aztec/aztec_foliage/'
AW = 'models/props/de_aztec/hr_aztec/aztec_walls/'
PALM = 'models/de_anubis/foliage/'
WEED = 'models/foliage/weeds/'

STOCK = {
    'models/cs_italy/foliage/fern/fern_plant_1.vmdl': ((-26, -23, -9), (21, 22, 17)),
    'models/cs_italy/foliage/fern/fern_plant_2.vmdl': ((-12, -10, -3), (12, 10, 17)),
    'models/cs_italy/foliage/generic/generic_leaf_plant_1.vmdl': ((-51, -43, -1), (49, 43, 47)),
    'models/cs_italy/foliage/hosta/hosta_plant_1.vmdl': ((-19, -23, -5), (24, 21, 19)),
    'models/cs_italy/foliage/taro/taro_leaf_plant_1.vmdl': ((-7, -6, -1), (8, 5, 7)),
    'models/cs_italy/foliage/taro/taro_leaf_plant_2.vmdl': ((-45, -40, -1), (36, 52, 94)),
    'models/cs_italy/foliage/tree/generic_tree_large_1.vmdl': ((-172, -197, -1), (168, 185, 487)),
    'models/de_anubis/foliage/palm_tree_01.vmdl': ((-146, -154, -0), (167, 122, 459)),
    'models/de_anubis/foliage/palm_tree_02.vmdl': ((-87, -119, -0), (171, 136, 397)),
    'models/de_anubis/foliage/palm_tree_03.vmdl': ((-157, -186, -1), (190, 164, 486)),
    'models/de_anubis/foliage/palm_tree_04.vmdl': ((-144, -139, -0), (167, 115, 357)),
    'models/de_anubis/foliage/palm_tree_hr_01.vmdl': ((-146, -154, -1), (167, 122, 459)),
    'models/de_anubis/foliage/palm_tree_hr_02.vmdl': ((-87, -119, -0), (171, 136, 397)),
    'models/de_anubis/foliage/palm_tree_small_01.vmdl': ((-75, -87, -0), (92, 70, 154)),
    'models/de_anubis/foliage/palm_tree_small_03.vmdl': ((-46, -44, 0), (57, 35, 98)),
    'models/de_anubis/foliage/palm_tree_small_05.vmdl': ((-24, -19, 0), (25, 26, 47)),
    'models/de_anubis/unique/water_wall02.vmdl': ((-32, -5, -100), (32, 2, 84)),
    'models/foliage/ground/ground_leaves_1.vmdl': ((-81, -67, 1), (87, 85, 3)),
    'models/foliage/ground/ground_leaves_2.vmdl': ((-29, -42, 0), (16, 38, 4)),
    'models/foliage/weeds/ground_mid_grass_01a.vmdl': ((-17, -18, 0), (19, 18, 39)),
    'models/foliage/weeds/ground_mid_grass_corner_01a.vmdl': ((-51, -12, -1), (10, 40, 52)),
    'models/foliage/weeds/ground_mid_grass_corner_01b.vmdl': ((-20, -13, -2), (18, 31, 42)),
    'models/foliage/weeds/ground_mid_line_grass_01a.vmdl': ((-16, -12, -0), (20, 10, 16)),
    'models/foliage/weeds/ground_mid_line_grass_01b.vmdl': ((-21, -12, -0), (19, 12, 26)),
    'models/foliage/weeds/ground_mid_plant_01a.vmdl': ((-8, -10, 0), (10, 8, 4)),
    'models/foliage/weeds/ground_mid_plant_02a.vmdl': ((-12, -8, -1), (10, 7, 29)),
    'models/foliage/weeds/ground_mid_plant_02b.vmdl': ((-7, -7, 0), (9, 7, 35)),
    'models/foliage/weeds/ground_mid_plant_02c.vmdl': ((-8, -7, -0), (7, 9, 29)),
    'models/foliage/weeds/ground_mid_plant_flowers_01a.vmdl': ((-7, -7, -0), (9, 10, 21)),
    'models/foliage/weeds/ground_mid_plant_flowers_01b.vmdl': ((-8, -9, -0), (8, 6, 16)),
    'models/foliage/weeds/ground_mid_plant_flowers_01c.vmdl': ((-7, -7, 0), (9, 9, 21)),
    'models/foliage/weeds/ground_mid_plant_flowers_01d.vmdl': ((-9, -8, 0), (6, 7, 21)),
    'models/foliage/weeds/ground_small_grass_01a.vmdl': ((-10, -8, 0), (10, 11, 8)),
    'models/foliage/weeds/ground_small_grass_01b.vmdl': ((-7, -11, -0), (9, 9, 7)),
    'models/foliage/weeds/ground_small_grass_01c.vmdl': ((-5, -5, 0), (4, 7, 3)),
    'models/foliage/weeds/ground_small_plant_01a.vmdl': ((-5, -5, 0), (5, 6, 2)),
    'models/foliage/weeds/ground_small_plant_01b.vmdl': ((-6, -4, 1), (5, 5, 2)),
    'models/foliage/weeds/ground_small_plant_01c.vmdl': ((-6, -6, 0), (6, 6, 2)),
    'models/foliage/weeds/ground_small_plant_02a.vmdl': ((-5, -5, 0), (6, 6, 28)),
    'models/foliage/weeds/ground_small_plant_02b.vmdl': ((-4, -4, -0), (3, 4, 13)),
    'models/foliage/weeds/ground_tall_grass_01a.vmdl': ((-27, -13, 0), (20, 13, 55)),
    'models/foliage/weeds/ground_tall_plant_flowers_01a.vmdl': ((-10, -13, 0), (12, 9, 75)),
    'models/foliage/weeds/ground_tall_plant_flowers_01b.vmdl': ((-21, -20, -0), (15, 15, 72)),
    'models/foliage/weeds/ground_tall_plant_flowers_01c.vmdl': ((-17, -12, -0), (15, 14, 47)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_01.vmdl': ((-51, -46, -1), (43, 46, 33)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_02.vmdl': ((-41, -41, -1), (43, 45, 35)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_03.vmdl': ((-40, -41, -1), (34, 38, 27)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_04.vmdl': ((-27, -23, -1), (29, 23, 26)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_05.vmdl': ((-17, -15, -1), (13, 20, 17)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_06.vmdl': ((-10, -13, -0), (12, 9, 7)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_01.vmdl': ((-47, -44, -1), (3, 46, 23)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_02.vmdl': ((-41, -37, -4), (4, 41, 20)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_03.vmdl': ((-40, -42, -2), (4, 39, 16)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_04.vmdl': ((-25, -23, -0), (2, 25, 10)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_05.vmdl': ((-20, -21, -1), (3, 23, 8)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_cluster_01.vmdl': ((-20, -22, -1), (2, 25, 7)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_cluster_02.vmdl': ((-20, -44, -1), (5, 44, 10)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_a_edge_cluster_03.vmdl': ((-16, -27, -2), (3, 33, 6)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_01.vmdl': ((-36, -40, -2), (37, 37, 24)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_02.vmdl': ((-39, -34, -2), (39, 34, 22)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_03.vmdl': ((-25, -26, -0), (30, 27, 25)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_04.vmdl': ((-20, -20, -0), (17, 23, 25)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_05.vmdl': ((-24, -21, -1), (14, 18, 14)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_01.vmdl': ((-35, -40, -2), (5, 39, 16)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_02.vmdl': ((-39, -34, -2), (3, 34, 16)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_03.vmdl': ((-30, -30, -0), (3, 31, 17)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_04.vmdl': ((-25, -20, -2), (2, 24, 17)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_05.vmdl': ((-24, -19, -2), (2, 22, 14)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_cluster_01.vmdl': ((-22, -31, -3), (2, 27, 13)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_cluster_02.vmdl': ((-30, -62, -2), (4, 69, 18)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_b_edge_cluster_03.vmdl': ((-27, -33, -1), (3, 52, 10)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_01.vmdl': ((-32, -28, -0), (33, 30, 18)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_02.vmdl': ((-32, -28, -0), (29, 26, 16)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_03.vmdl': ((-19, -19, -0), (26, 23, 15)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_edge_01.vmdl': ((-32, -24, -0), (3, 25, 15)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_edge_02.vmdl': ((-34, -28, -0), (3, 24, 16)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_edge_03.vmdl': ((-21, -17, -0), (2, 18, 11)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_edge_cluster_01.vmdl': ((-27, -47, -0), (2, 32, 14)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_fern_style_c_edge_cluster_02.vmdl': ((-22, -68, -0), (3, 16, 9)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tree_dead_01.vmdl': ((-79, -54, -24), (90, 561, 89)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_edge_01.vmdl': ((-6, -29, -12), (17, 27, 5)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_edge_hanging_01.vmdl': ((-5, -13, -58), (16, 15, 5)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_edge_hanging_02.vmdl': ((-7, -15, -126), (16, 17, 5)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_edge_hanging_03.vmdl': ((-6, -29, -36), (19, 27, 5)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_ground_patch_01.vmdl': ((-30, -34, 0), (29, 25, 6)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_ground_patch_edge_01.vmdl': ((0, -30, 0), (35, 29, 8)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_single_vine_01.vmdl': ((-5, -6, -125), (-1, 6, 2)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_single_vine_02.vmdl': ((-2, -5, -69), (0, 5, 0)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage2_tree_medium_01.vmdl': ((-60, -49, -93), (3, 47, 154)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage3_medium_01.vmdl': ((-41, -45, -20), (9, 41, 30)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage3_medium_02.vmdl': ((-43, -44, -17), (6, 40, 38)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage3_medium_03.vmdl': ((-45, -40, -28), (4, 41, 29)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage3_small_01.vmdl': ((-29, -31, -0), (30, 32, 24)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage3_small_02.vmdl': ((-31, -30, -0), (36, 39, 27)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_large_01.vmdl': ((-56, -44, -0), (48, 38, 117)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_large_02.vmdl': ((-31, -40, -0), (34, 43, 149)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_medium_01.vmdl': ((-26, -29, -0), (24, 24, 66)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_medium_02.vmdl': ((-28, -22, 0), (26, 28, 65)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_small_01.vmdl': ((-20, -15, -0), (12, 14, 33)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_tropical_foliage_small_02.vmdl': ((-19, -15, -0), (10, 14, 28)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_dead_01.vmdl': ((-56, -52, -1), (41, 57, 58)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_dead_corner_01.vmdl': ((-53, -50, -2), (50, 50, 37)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_dead_corner_overhung_01.vmdl': ((-52, -50, -77), (52, 41, 54)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_dead_edge_01.vmdl': ((-47, -50, -2), (52, 8, 66)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_dead_edge_overhung_01.vmdl': ((-43, -58, -77), (52, 8, 47)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_large_01.vmdl': ((-68, -80, -6), (61, 80, 44)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_large_corner_01.vmdl': ((-75, -80, -6), (61, 53, 35)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_large_corner_overhung_01.vmdl': ((-67, -80, -77), (61, 47, 35)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_large_edge_01.vmdl': ((-68, -80, -6), (61, 9, 35)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_large_edge_overhung_01.vmdl': ((-68, -80, -77), (61, 9, 35)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_small_01.vmdl': ((-39, -46, -5), (38, 42, 33)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_small_corner_01.vmdl': ((-34, -45, -5), (39, 30, 31)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_small_corner_overhung_01.vmdl': ((-37, -42, -41), (39, 30, 31)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_small_edge_01.vmdl': ((-38, -42, -5), (39, 11, 31)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztec_yucca_small_edge_overhung_01.vmdl': ((-38, -42, -41), (39, 11, 31)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztex_fern_style_a_wall_scatter_01.vmdl': ((-9, -59, 9), (2, 45, 119)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/aztex_fern_style_b_wall_scatter_01.vmdl': ((-8, -36, 18), (1, 48, 103)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_large_01.vmdl': ((-538, -560, -2), (491, 580, 1035)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_large_01_vines.vmdl': ((-219, -153, -72), (214, 307, 657)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_large_roots_01.vmdl': ((-153, -185, -169), (168, 161, -2)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_01.vmdl': ((-257, -264, 0), (327, 304, 590)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_01_vines.vmdl': ((-109, -27, 35), (136, 34, 449)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_02.vmdl': ((-171, -248, 0), (206, 239, 1075)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_02_vines.vmdl': ((-60, -92, 126), (62, 30, 939)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_03.vmdl': ((-292, -277, 0), (324, 329, 869)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_03_vines.vmdl': ((-87, -30, 145), (146, 199, 737)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_roots_01.vmdl': ((-81, -102, -92), (92, 91, 0)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_roots_02.vmdl': ((-88, -108, -231), (115, 117, 0)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_roots_03.vmdl': ((-81, -95, -161), (87, 91, 0)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_medium_roots_04.vmdl': ((-114, -106, -245), (87, 99, 1)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_small_01.vmdl': ((-162, -136, -0), (127, 157, 403)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_small_02.vmdl': ((-171, -160, -0), (147, 138, 610)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_small_roots_01.vmdl': ((-41, -38, -42), (47, 41, -0)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_banyan_small_roots_02.vmdl': ((-56, -63, -171), (44, 30, 1)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_bundle_01.vmdl': ((-40, -43, -100), (39, 38, 1)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_bundle_02.vmdl': ((-21, -28, -108), (18, 21, 1)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_edge_01.vmdl': ((-40, 2, -88), (33, 13, 13)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_edge_02.vmdl': ((-22, 3, -93), (13, 13, 13)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_edge_03.vmdl': ((-54, 6, -27), (53, 13, 13)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_edge_04.vmdl': ((-39, 3, -70), (33, 13, 13)),
    'models/props/de_aztec/hr_aztec/aztec_foliage/hr_aztec_roots_edge_05.vmdl': ((-54, 7, -14), (53, 13, 13)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_01.vmdl': ((-9, -9, -4), (9, 9, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_02.vmdl': ((-11, -9, -5), (11, 9, 5)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_03.vmdl': ((-11, -10, -4), (11, 10, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_04.vmdl': ((-10, -9, -4), (10, 9, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_05.vmdl': ((-6, -10, -4), (6, 10, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_06.vmdl': ((-10, -12, -4), (10, 12, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_07.vmdl': ((-10, -11, -4), (10, 11, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_08.vmdl': ((-12, -8, -5), (12, 8, 5)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_09.vmdl': ((-11, -7, -4), (11, 7, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_10.vmdl': ((-13, -8, -5), (13, 8, 5)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_11.vmdl': ((-8, -10, -4), (8, 10, 4)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_12.vmdl': ((-13, -11, -5), (13, 11, 5)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_01.vmdl': ((-67, -70, -2), (77, 73, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_02.vmdl': ((-63, -62, -2), (73, 73, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_03.vmdl': ((-71, -67, -2), (76, 79, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_04.vmdl': ((-29, -37, -2), (45, 41, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_05.vmdl': ((-39, -30, -2), (41, 29, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_06.vmdl': ((-31, -38, -2), (26, 29, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_ground_rock_01_rock_cluster_07.vmdl': ((-35, -38, -2), (33, 38, 2)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_01.vmdl': ((-10, -7, -11), (10, 7, 11)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_02.vmdl': ((-9, -9, -16), (10, 9, 16)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_03.vmdl': ((-10, -13, -14), (11, 13, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_04.vmdl': ((-9, -8, -14), (10, 8, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_05.vmdl': ((-9, -11, -14), (10, 11, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_angled_stone_06.vmdl': ((-9, -13, -15), (10, 13, 15)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_collapsed_edge_01.vmdl': ((-5, -68, -8), (64, 67, 68)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_collapsed_pile_01.vmdl': ((-26, -50, -18), (24, 50, 19)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_rubble_corner_01.vmdl': ((-57, -98, -4), (70, 3, 263)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_rubble_corner_02.vmdl': ((-99, -72, 2), (46, 2, 263)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_rubble_corner_03.vmdl': ((-9, 9, -44), (76, 141, 137)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_rubble_corner_04.vmdl': ((-1, -126, -4), (72, -6, 131)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_rubble_corner_05.vmdl': ((-129, -1, 4), (0, 126, 136)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_01.vmdl': ((-10, -13, -15), (10, 13, 15)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_02.vmdl': ((-10, -11, -14), (10, 11, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_03.vmdl': ((-10, -8, -14), (10, 8, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_04.vmdl': ((-11, -13, -14), (11, 13, 14)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_05.vmdl': ((-10, -9, -16), (10, 9, 16)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_03_stone_06.vmdl': ((-10, -7, -11), (10, 7, 11)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone01_bridge_foundation_01.vmdl': ((-3, -2, 0), (66, 193, 198)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone01_bridge_foundation_02.vmdl': ((-3, -2, -0), (67, 193, 166)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_high_corner_erroded.vmdl': ((-34, -35, -2), (34, 34, 129)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_high_end.vmdl': ((-2, -35, -2), (67, 3, 127)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_high_flat.vmdl': ((-67, -34, -4), (2, 2, 15)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_low_corner_erroded.vmdl': ((-34, -34, -2), (34, 33, 31)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_low_flat.vmdl': ((-66, -34, -5), (2, 2, 15)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_med_corner_erroded.vmdl': ((-34, -34, -2), (34, 34, 70)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_med_end.vmdl': ((-2, -34, -1), (66, 2, 64)),
    'models/props/de_aztec/hr_aztec/aztec_walls/aztec_wall_stone_01_32x64_med_flat.vmdl': ((-69, -34, -9), (5, 2, 12)),
}

BANYAN_L = [AZ + 'hr_aztec_banyan_large_01.vmdl']
BANYAN_M = [AZ + 'hr_aztec_banyan_medium_0%d.vmdl' % k for k in (1, 2, 3)]
BANYAN_S = [AZ + 'hr_aztec_banyan_small_0%d.vmdl' % k for k in (1, 2)]
ROOTS = [AZ + 'hr_aztec_banyan_medium_roots_01.vmdl', AZ + 'hr_aztec_banyan_small_roots_01.vmdl']
PALMS = [PALM + 'palm_tree_0%d.vmdl' % k for k in (1, 2, 3, 4)]
PALMS_SMALL = [PALM + 'palm_tree_small_01.vmdl', PALM + 'palm_tree_small_03.vmdl']
TROPICAL_L = [AZ + 'aztec_tropical_foliage_large_0%d.vmdl' % k for k in (1, 2)]
TROPICAL_M = [AZ + 'aztec_tropical_foliage_medium_0%d.vmdl' % k for k in (1, 2)]
TROPICAL_S = [AZ + 'aztec_tropical_foliage_small_0%d.vmdl' % k for k in (1, 2)] + [AZ + 'aztec_tropical_foliage3_small_0%d.vmdl' % k for k in (1, 2)]
FERNS = [AZ + 'aztec_fern_style_a_0%d.vmdl' % k for k in (1, 2, 3, 4)] + [AZ + 'aztec_fern_style_b_0%d.vmdl' % k for k in (1, 2, 3)] + \
        [AZ + 'aztec_fern_style_c_0%d.vmdl' % k for k in (1, 2)]
YUCCA = [AZ + 'aztec_yucca_large_01.vmdl', AZ + 'aztec_yucca_small_01.vmdl']
TARO = ['models/cs_italy/foliage/taro/taro_leaf_plant_2.vmdl', 'models/cs_italy/foliage/generic/generic_leaf_plant_1.vmdl']
WEEDS = [WEED + 'ground_tall_grass_01a.vmdl', WEED + 'ground_mid_grass_01a.vmdl', WEED + 'ground_tall_plant_flowers_01b.vmdl']
ROCKS = [AW + 'aztec_wall_03_stone_0%d.vmdl' % k for k in (1, 2, 3, 4, 5, 6)]
ROCK_CLUSTERS = [AW + 'aztec_ground_rock_01_rock_cluster_0%d.vmdl' % k for k in (1, 2, 3, 4, 5, 6, 7)]
RUBBLE = [AW + 'aztec_wall_03_collapsed_pile_01.vmdl', AW + 'aztec_wall_03_collapsed_edge_01.vmdl']
WATER_WALL = 'models/de_anubis/unique/water_wall02.vmdl'

# trunk radius (collision footprint) by model
TRUNK = {AZ + 'hr_aztec_banyan_large_01.vmdl': 95.0, AZ + 'hr_aztec_banyan_medium_01.vmdl': 46.0, AZ + 'hr_aztec_banyan_medium_02.vmdl': 40.0,
         AZ + 'hr_aztec_banyan_medium_03.vmdl': 50.0, AZ + 'hr_aztec_banyan_small_01.vmdl': 24.0, AZ + 'hr_aztec_banyan_small_02.vmdl': 26.0}
for _m in PALMS: TRUNK[_m] = 13.0
for _m in PALMS_SMALL: TRUNK[_m] = 8.0

# our props that are not built yet: (lo, hi), conservative. Assumed origins: on the ground at the footprint centre; long axis x.
FALLBACK = {
    'm2_gun': ((-34, -6, 0), (64, 16, 14)), 'm3_tripod': ((-36, -32, 0), (42, 32, 31)), 'dshk_gun': ((-39, -8, -4), (82, 8, 14)),
    'dshk_mount': ((-48, -46, 0), (50, 46, 64)), 'quad50_mount': ((-76, -66, 0), (76, 66, 74)), 'quad50_gun': ((-30, -50, -14), (64, 50, 20)),
    'hooch_a': ((-132, -102, -4), (132, 102, 170)), 'hooch_b': ((-112, -92, -4), (112, 92, 160)), 'hooch_c': ((-152, -112, -4), (152, 112, 190)),
    'camp_hut': ((-156, -116, 0), (156, 116, 170)), 'school': ((-160, -110, 0), (160, 110, 170)), 'shrine': ((-24, -20, 0), (24, 20, 104)),
    'well': ((-40, -40, 0), (40, 40, 96)), 'bamboo_fence': ((-66, -4, 0), (66, 6, 60)), 'bamboo_fence_64': ((-34, -4, 0), (34, 6, 60)),
    'rice_basket': ((-14, -14, 0), (14, 14, 18)), 'water_jar': ((-14, -14, 0), (14, 14, 30)), 'drying_rack': ((-54, -8, 0), (54, 8, 72)),
    'haystack': ((-46, -46, 0), (46, 46, 84)), 'pig_pen': ((-74, -54, 0), (74, 54, 70)), 'ox_cart': ((-64, -42, 0), (100, 42, 92)),
    'sampan': ((-122, -32, 0), (122, 32, 58)), 'sampan_open': ((-122, -32, 0), (122, 32, 32)), 'fish_trap': ((-22, -10, 0), (22, 10, 20)),
    'market_stall': ((-56, -46, 0), (56, 46, 104)), 'propaganda_board': ((-4, -64, 0), (4, 64, 110)), 'punji_stakes': ((-40, -40, -8), (40, 40, 22)),
    'cook_fire': ((-30, -30, 0), (30, 30, 46)), 'camo_net': ((-282, -212, 0), (282, 212, 150)),
    'rotor_hip': ((-345, -345, -6), (345, 345, 10)), 'tailrotor_hip': ((-60, -6, -60), (60, 6, 60)),
    'heli_hip_gun': ((-566, -140, 0), (305, 140, 194)), 'wreck_hip': ((-566, -200, 0), (305, 200, 150)), 'wreck_huey': ((-470, -150, 0), (262, 150, 120)),
    'sandbag_wall': ((-32, -9, 0), (32, 9, 27)), 'sandbag_wall_b': ((-32, -9, 0), (32, 9, 27)), 'sandbag_wall_128': ((-64, -9, 0), (64, 9, 27)),
    'sandbag_low': ((-32, -9, 0), (32, 9, 18)), 'sandbag_low_128': ((-64, -9, 0), (64, 9, 18)),
    'elephant_grass_a': ((-48, -48, 0), (48, 48, 90)), 'elephant_grass_b': ((-48, -48, 0), (48, 48, 90)), 'elephant_grass_c': ((-48, -48, 0), (48, 48, 90)),
    'rice_clump_a': ((-30, -30, 0), (30, 30, 30)), 'rice_clump_b': ((-30, -30, 0), (30, 30, 30)), 'reeds': ((-36, -36, 0), (36, 36, 80)),
    'bamboo_clump': ((-50, -50, 0), (50, 50, 320)), 'rubber_tree': ((-110, -110, 0), (110, 110, 460)), 'log_fallen': ((-110, -14, 0), (110, 14, 26)),
    'dead_tree': ((-70, -70, 0), (70, 70, 330)), 'vine_curtain': ((-48, -6, -150), (48, 6, 0)), 'root_tangle': ((-50, -40, 0), (50, 40, 34)),
    'flag_pole': ((-8, -8, 0), (40, 8, 260)), 'supply_crate': ((-26, -18, 0), (26, 18, 30)),
    'truss_span': ((-300, -80, -24), (300, 80, 150)), 'bridge_pier': ((-40, -90, 0), (40, 90, 100)), 'checkpoint': ((-70, -50, 0), (70, 50, 110)),
    'french_bunker': ((-110, -110, 0), (110, 110, 110)), 'khmer_gate': ((-120, -40, 0), (120, 40, 230)), 'khmer_tower': ((-130, -130, 0), (130, 130, 420)),
    'naga_balustrade': ((-64, -10, 0), (64, 10, 48)), 'guardian_statue': ((-22, -22, 0), (22, 22, 96)), 'fallen_blocks': ((-60, -50, 0), (60, 50, 44)),
    'stone_stairs': ((-64, -64, 0), (64, 64, 64)), 'lintel_fallen': ((-80, -18, 0), (80, 18, 30)),
    'c123_fuselage': ((-460, -80, 0), (460, 80, 170)), 'c123_wing': ((-300, -100, 0), (300, 100, 60)), 'c123_engine': ((-60, -36, 0), (60, 36, 70)),
    'pbr_wreck': ((-190, -70, 0), (190, 70, 110)), 'truck_wreck': ((-130, -50, 0), (130, 50, 110)), 'm113_hulk': ((-100, -56, 0), (100, 56, 90)),
    'cargo_pallet': ((-52, -44, 0), (52, 44, 60)), 'parachute_silk': ((-120, -100, 0), (120, 100, 20)),
}
# footprints the placer should use instead of the full bounds: the guard tower's bounds are widened to +-166 by the sandbag rows
# on its platform 266 u up (they stick out radially); on the ground it is the four legs and the ladder
FOOTPRINT = {'guard_tower': ((-112.0, -92.0, 0.0), (92.0, 92.0, 353.0))}
TRUNK_MV = {'rubber_tree': 10.0, 'dead_tree': 12.0, 'bamboo_clump': 34.0}
APACHE = dict(model='models/vehicles/apache/apache.vmdl', lo=(-420.0, -303.0, 0.0), hi=(290.0, 303.0, 190.0), rotor_r=303.0)


def mv(name):
    return 'models/mv/%s/%s.vmdl' % (name, name)


def bounds_table(props_json):
    """-> (placer bounds table, built props): the measured stock models, the Apache (out/apache.json when present) and fallbacks
    for props props.json does not have yet"""
    built = json.load(open(props_json)) if props_json and os.path.exists(props_json) else {}
    t = dict(STOCK)
    for n, b in FALLBACK.items():
        if n not in built: t[mv(n)] = b
    ap = os.path.join(os.path.dirname(os.path.abspath(props_json)), 'apache.json') if props_json else ''
    lo, hi = APACHE['lo'], APACHE['hi']
    if ap and os.path.exists(ap):
        try:
            a = json.load(open(ap))
            bb = a.get('bounds', a)                     # the body without the rotor disc
            lo = tuple(bb.get('mins', lo)); hi = tuple(bb.get('maxs', hi))
        except Exception: pass
    t[APACHE['model']] = (lo, hi)
    t.update({mv(n): b for n, b in FOOTPRINT.items()})
    return t, built
