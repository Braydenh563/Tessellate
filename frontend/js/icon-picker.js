// icon-picker.js: the one icon and emoji picker (MINDMAP_PLAN.md decisions
// 43 to 46; INBOX 642, the owner: "an emoji and icon widget library which can
// be dragged and placed in the whiteboard and mindmap and which are also
// available in text editors and formatting toolbars").
//
// One lazy module, fetched with its stylesheet on first use by
// `pickIconOrEmoji` (editor.js), so every surface that offers an icon or an emoji opens
// the same panel: a map topic's icon slot, the board's and the map's Insert
// menu (a placed sticker), the note and document formatting toolbars and the
// "/" menu. Taken from Photoshop's Glyphs panel (search, a Recent row) and
// Miro's icon panel (drag a tile onto the canvas).
//
// Its anatomy, from the recipe index's own rows:
//
//   - the popover shell (`.help-popover`, placed by `placeHelpPopover`,
//     lifted to <body>), with a dialog head and its X;
//   - a `.search-field` that filters as you type, over names and categories;
//   - a `.tabs-line` of two under the head, Emoji and Icons, when a surface offers both;
//   - one `role="listbox"` grid of `role="option"` tiles under group heads,
//     Recent first (this device, twenty: a per-person convenience, so local
//     storage, and the panel draws correctly without it).
//
// **Nothing is fetched.** The icons are the vendored Phosphor font's names,
// read off its own stylesheet (`/vendor/phosphor/style.css`, already loaded at
// boot), so there is no second list to keep in step with the font. The emoji
// are a curated set with their Unicode names, written as escapes, as
// `DOC_EMOJI_SOURCE` (documents-prose.js) is.
//
// **Keys:** arrows move through the grid (Up and Down by a row), Home and End,
// Enter or Space picks, Escape closes and hands focus back to whatever opened
// it; typing a letter in the grid goes back to the search field. **Drag:**
// every tile carries its glyph as plain text (a drop into any text box inserts
// it: an emoji as itself, an icon as `:ph-name:`) and as
// `application/x-memorymap-icon`, which the board and the map read.
//
// Every builder uses createElement and textContent: nothing here parses markup.

//: The curated emoji, by group: `[key, heading, "name=glyph,..."]`. Names are
//: the Unicode names, lower case with underscores, which is what search reads.
const ICON_EMOJI_SOURCE = [
  ["smileys", "Smileys",
    "grinning_face=\u{1F600},smiling_face_with_open_mouth=\u{1F603}," +
    "smiling_face_with_open_mouth_and_smiling_eyes=\u{1F604}," +
    "grinning_face_with_smiling_eyes=\u{1F601}," +
    "smiling_face_with_open_mouth_and_tightly_closed_eyes=\u{1F606}," +
    "smiling_face_with_open_mouth_and_cold_sweat=\u{1F605},face_with_tears_of_joy=\u{1F602}," +
    "rolling_on_the_floor_laughing=\u{1F923},slightly_smiling_face=\u{1F642}," +
    "upside_down_face=\u{1F643},winking_face=\u{1F609},smiling_face_with_smiling_eyes=\u{1F60A}," +
    "smiling_face_with_halo=\u{1F607},smiling_face_with_smiling_eyes_and_three_hearts=\u{1F970}," +
    "smiling_face_with_heart_shaped_eyes=\u{1F60D},grinning_face_with_star_eyes=\u{1F929}," +
    "face_throwing_a_kiss=\u{1F618},face_savouring_delicious_food=\u{1F60B}," +
    "face_with_stuck_out_tongue=\u{1F61B},grinning_face_with_one_large_and_one_small_eye=\u{1F92A}," +
    "hugging_face=\u{1F917},thinking_face=\u{1F914},face_with_finger_covering_closed_lips=\u{1F92B}," +
    "zipper_mouth_face=\u{1F910},face_with_one_eyebrow_raised=\u{1F928},neutral_face=\u{1F610}," +
    "expressionless_face=\u{1F611},face_without_mouth=\u{1F636},smirking_face=\u{1F60F}," +
    "unamused_face=\u{1F612},face_with_rolling_eyes=\u{1F644},grimacing_face=\u{1F62C}," +
    "relieved_face=\u{1F60C},pensive_face=\u{1F614},sleepy_face=\u{1F62A},sleeping_face=\u{1F634}," +
    "face_with_medical_mask=\u{1F637},face_with_thermometer=\u{1F912},nerd_face=\u{1F913}," +
    "face_with_monocle=\u{1F9D0},smiling_face_with_sunglasses=\u{1F60E}," +
    "face_with_party_horn_and_party_hat=\u{1F973},face_with_cowboy_hat=\u{1F920}," +
    "confused_face=\u{1F615},worried_face=\u{1F61F},slightly_frowning_face=\u{1F641}," +
    "face_with_open_mouth=\u{1F62E},astonished_face=\u{1F632},flushed_face=\u{1F633}," +
    "face_with_pleading_eyes=\u{1F97A},crying_face=\u{1F622},loudly_crying_face=\u{1F62D}," +
    "face_screaming_in_fear=\u{1F631},shocked_face_with_exploding_head=\u{1F92F}," +
    "face_with_open_mouth_and_cold_sweat=\u{1F630},overheated_face=\u{1F975},freezing_face=\u{1F976}," +
    "face_with_uneven_eyes_and_wavy_mouth=\u{1F974},tired_face=\u{1F62B},yawning_face=\u{1F971}," +
    "face_with_look_of_triumph=\u{1F624},pouting_face=\u{1F621},angry_face=\u{1F620}," +
    "money_mouth_face=\u{1F911},skull=\u{1F480},pile_of_poo=\u{1F4A9},clown_face=\u{1F921}," +
    "ghost=\u{1F47B},extraterrestrial_alien=\u{1F47D},robot_face=\u{1F916}," +
    "see_no_evil_monkey=\u{1F648},hear_no_evil_monkey=\u{1F649},speak_no_evil_monkey=\u{1F64A},"],
  ["people", "People and hands",
    "waving_hand_sign=\u{1F44B},raised_hand=\u{270B},ok_hand_sign=\u{1F44C}," +
    "victory_hand=\u{270C}\u{FE0F},hand_with_index_and_middle_fingers_crossed=\u{1F91E}," +
    "white_up_pointing_index=\u{261D}\u{FE0F},white_right_pointing_backhand_index=\u{1F449}," +
    "white_left_pointing_backhand_index=\u{1F448},white_up_pointing_backhand_index=\u{1F446}," +
    "white_down_pointing_backhand_index=\u{1F447},thumbs_up_sign=\u{1F44D},thumbs_down_sign=\u{1F44E}," +
    "fisted_hand_sign=\u{1F44A},clapping_hands_sign=\u{1F44F}," +
    "person_raising_both_hands_in_celebration=\u{1F64C},open_hands_sign=\u{1F450}," +
    "person_with_folded_hands=\u{1F64F},handshake=\u{1F91D},flexed_biceps=\u{1F4AA}," +
    "writing_hand=\u{270D}\u{FE0F},eyes=\u{1F440},brain=\u{1F9E0},baby=\u{1F476},child=\u{1F9D2}," +
    "adult=\u{1F9D1},man=\u{1F468},woman=\u{1F469},older_adult=\u{1F9D3},family=\u{1F46A}," +
    "busts_in_silhouette=\u{1F465},bust_in_silhouette=\u{1F464}," +
    "speaking_head_in_silhouette=\u{1F5E3}\u{FE0F},personal_computer=\u{1F9D1}\u{200D}\u{1F4BB}," +
    "school=\u{1F9D1}\u{200D}\u{1F3EB},microscope=\u{1F9D1}\u{200D}\u{1F52C}," +
    "cooking=\u{1F9D1}\u{200D}\u{1F373},staff_of_aesculapius=\u{1F9D1}\u{200D}\u{2695}\u{FE0F}," +
    "runner=\u{1F3C3},pedestrian=\u{1F6B6},dancer=\u{1F483},person_in_lotus_position=\u{1F9D8},"],
  ["nature", "Animals and nature",
    "cat_face=\u{1F431},dog_face=\u{1F436},fox_face=\u{1F98A},bear_face=\u{1F43B}," +
    "panda_face=\u{1F43C},koala=\u{1F428},tiger_face=\u{1F42F},lion_face=\u{1F981}," +
    "unicorn_face=\u{1F984},horse_face=\u{1F434},pig_face=\u{1F437},cow_face=\u{1F42E}," +
    "frog_face=\u{1F438},monkey_face=\u{1F435},chicken=\u{1F414},penguin=\u{1F427},bird=\u{1F426}," +
    "eagle=\u{1F985},owl=\u{1F989},honeybee=\u{1F41D},butterfly=\u{1F98B},lady_beetle=\u{1F41E}," +
    "turtle=\u{1F422},snake=\u{1F40D},octopus=\u{1F419},spouting_whale=\u{1F433},dolphin=\u{1F42C}," +
    "shark=\u{1F988},tropical_fish=\u{1F420},seedling=\u{1F331},evergreen_tree=\u{1F332}," +
    "deciduous_tree=\u{1F333},palm_tree=\u{1F334},cactus=\u{1F335},four_leaf_clover=\u{1F340}," +
    "maple_leaf=\u{1F341},fallen_leaf=\u{1F342},rose=\u{1F339},sunflower=\u{1F33B}," +
    "cherry_blossom=\u{1F338},tulip=\u{1F337},herb=\u{1F33F},mushroom=\u{1F344}," +
    "earth_globe_europe_africa=\u{1F30D},crescent_moon=\u{1F319},black_sun_with_rays=\u{2600}\u{FE0F}," +
    "white_medium_star=\u{2B50}\u{FE0F},glowing_star=\u{1F31F},cloud=\u{2601}\u{FE0F}," +
    "rainbow=\u{1F308},high_voltage_sign=\u{26A1}\u{FE0F},snowflake=\u{2744}\u{FE0F},fire=\u{1F525}," +
    "droplet=\u{1F4A7},water_wave=\u{1F30A},"],
  ["food", "Food and drink",
    "red_apple=\u{1F34E},tangerine=\u{1F34A},lemon=\u{1F34B},banana=\u{1F34C},watermelon=\u{1F349}," +
    "grapes=\u{1F347},strawberry=\u{1F353},cherries=\u{1F352},peach=\u{1F351},pineapple=\u{1F34D}," +
    "coconut=\u{1F965},avocado=\u{1F951},aubergine=\u{1F346},carrot=\u{1F955},ear_of_maize=\u{1F33D}," +
    "hot_pepper=\u{1F336}\u{FE0F},broccoli=\u{1F966},bread=\u{1F35E},cheese_wedge=\u{1F9C0}," +
    "egg=\u{1F95A},cooking=\u{1F373},bacon=\u{1F953},hamburger=\u{1F354},french_fries=\u{1F35F}," +
    "slice_of_pizza=\u{1F355},taco=\u{1F32E},sandwich=\u{1F96A},spaghetti=\u{1F35D}," +
    "steaming_bowl=\u{1F35C},sushi=\u{1F363},bento_box=\u{1F371},curry_and_rice=\u{1F35B}," +
    "shortcake=\u{1F370},birthday_cake=\u{1F382},doughnut=\u{1F369},cookie=\u{1F36A}," +
    "chocolate_bar=\u{1F36B},lollipop=\u{1F36D},popcorn=\u{1F37F},hot_beverage=\u{2615}\u{FE0F}," +
    "teacup_without_handle=\u{1F375},beverage_box=\u{1F9C3},beer_mug=\u{1F37A},wine_glass=\u{1F377}," +
    "cocktail_glass=\u{1F378},cup_with_straw=\u{1F964},"],
  ["activity", "Activities",
    "party_popper=\u{1F389},confetti_ball=\u{1F38A},balloon=\u{1F388},wrapped_present=\u{1F381}," +
    "ribbon=\u{1F380},trophy=\u{1F3C6},sports_medal=\u{1F3C5},first_place_medal=\u{1F947}," +
    "second_place_medal=\u{1F948},third_place_medal=\u{1F949},soccer_ball=\u{26BD}\u{FE0F}," +
    "basketball_and_hoop=\u{1F3C0},american_football=\u{1F3C8},baseball=\u{26BE}\u{FE0F}," +
    "tennis_racquet_and_ball=\u{1F3BE},volleyball=\u{1F3D0},bowling=\u{1F3B3}," +
    "table_tennis_paddle_and_ball=\u{1F3D3},boxing_glove=\u{1F94A},direct_hit=\u{1F3AF}," +
    "video_game=\u{1F3AE},game_die=\u{1F3B2},black_chess_pawn=\u{265F}\u{FE0F}," +
    "jigsaw_puzzle_piece=\u{1F9E9},artist_palette=\u{1F3A8},performing_arts=\u{1F3AD}," +
    "clapper_board=\u{1F3AC},microphone=\u{1F3A4},headphone=\u{1F3A7},musical_note=\u{1F3B5}," +
    "multiple_musical_notes=\u{1F3B6},musical_keyboard=\u{1F3B9},guitar=\u{1F3B8}," +
    "drum_with_drumsticks=\u{1F941},violin=\u{1F3BB},circus_tent=\u{1F3AA},bicyclist=\u{1F6B4}," +
    "swimmer=\u{1F3CA},surfer=\u{1F3C4},skier=\u{26F7}\u{FE0F},"],
  ["travel", "Travel and places",
    "automobile=\u{1F697},taxi=\u{1F695},bus=\u{1F68C},police_car=\u{1F693},ambulance=\u{1F691}," +
    "fire_engine=\u{1F692},delivery_truck=\u{1F69A},bicycle=\u{1F6B2},scooter=\u{1F6F4}," +
    "racing_motorcycle=\u{1F3CD}\u{FE0F},steam_locomotive=\u{1F682},train=\u{1F686},metro=\u{1F687}," +
    "airplane=\u{2708}\u{FE0F},airplane_departure=\u{1F6EB}\u{FE0F}," +
    "airplane_arriving=\u{1F6EC}\u{FE0F},rocket=\u{1F680},flying_saucer=\u{1F6F8}," +
    "helicopter=\u{1F681},sailboat=\u{26F5}\u{FE0F},ship=\u{1F6A2},anchor=\u{2693}\u{FE0F}," +
    "vertical_traffic_light=\u{1F6A6},construction_sign=\u{1F6A7},house_building=\u{1F3E0}," +
    "house_with_garden=\u{1F3E1},office_building=\u{1F3E2},school=\u{1F3EB},hospital=\u{1F3E5}," +
    "bank=\u{1F3E6},convenience_store=\u{1F3EA},factory=\u{1F3ED},european_castle=\u{1F3F0}," +
    "tokyo_tower=\u{1F5FC},statue_of_liberty=\u{1F5FD},church=\u{26EA}\u{FE0F}," +
    "mountain=\u{26F0}\u{FE0F},snow_capped_mountain=\u{1F3D4}\u{FE0F}," +
    "beach_with_umbrella=\u{1F3D6}\u{FE0F},desert_island=\u{1F3DD}\u{FE0F},camping=\u{1F3D5}\u{FE0F}," +
    "world_map=\u{1F5FA}\u{FE0F},compass=\u{1F9ED},globe_with_meridians=\u{1F310},"],
  ["objects", "Objects",
    "watch=\u{231A}\u{FE0F},mobile_phone=\u{1F4F1},personal_computer=\u{1F4BB}," +
    "keyboard=\u{2328}\u{FE0F},desktop_computer=\u{1F5A5}\u{FE0F},printer=\u{1F5A8}\u{FE0F}," +
    "three_button_mouse=\u{1F5B1}\u{FE0F},floppy_disk=\u{1F4BE},optical_disc=\u{1F4BF}," +
    "camera=\u{1F4F7},movie_camera=\u{1F3A5},television=\u{1F4FA},radio=\u{1F4FB}," +
    "black_telephone=\u{260E}\u{FE0F},telephone_receiver=\u{1F4DE},battery=\u{1F50B}," +
    "electric_plug=\u{1F50C},electric_light_bulb=\u{1F4A1},electric_torch=\u{1F526}," +
    "candle=\u{1F56F}\u{FE0F},open_book=\u{1F4D6},books=\u{1F4DA},notebook=\u{1F4D3},ledger=\u{1F4D2}," +
    "closed_book=\u{1F4D5},green_book=\u{1F4D7},blue_book=\u{1F4D8},orange_book=\u{1F4D9}," +
    "newspaper=\u{1F4F0},memo=\u{1F4DD},pencil=\u{270F}\u{FE0F}," +
    "lower_left_ballpoint_pen=\u{1F58A}\u{FE0F},lower_left_fountain_pen=\u{1F58B}\u{FE0F}," +
    "lower_left_paintbrush=\u{1F58C}\u{FE0F},paperclip=\u{1F4CE},pushpin=\u{1F4CC}," +
    "round_pushpin=\u{1F4CD},black_scissors=\u{2702}\u{FE0F},calendar=\u{1F4C5}," +
    "tear_off_calendar=\u{1F4C6},spiral_calendar_pad=\u{1F5D3}\u{FE0F},clipboard=\u{1F4CB}," +
    "file_folder=\u{1F4C1},open_file_folder=\u{1F4C2},card_index_dividers=\u{1F5C2}\u{FE0F}," +
    "chart_with_upwards_trend=\u{1F4C8},chart_with_downwards_trend=\u{1F4C9},bar_chart=\u{1F4CA}," +
    "e_mail_symbol=\u{1F4E7},envelope=\u{2709}\u{FE0F},inbox_tray=\u{1F4E5},outbox_tray=\u{1F4E4}," +
    "package=\u{1F4E6},closed_mailbox_with_raised_flag=\u{1F4EB},postbox=\u{1F4EE},bell=\u{1F514}," +
    "cheering_megaphone=\u{1F4E3},lock=\u{1F512},open_lock=\u{1F513},key=\u{1F511}," +
    "old_key=\u{1F5DD}\u{FE0F},hammer=\u{1F528},wrench=\u{1F527},nut_and_bolt=\u{1F529}," +
    "gear=\u{2699}\u{FE0F},toolbox=\u{1F9F0},magnet=\u{1F9F2},link_symbol=\u{1F517}," +
    "left_pointing_magnifying_glass=\u{1F50D},microscope=\u{1F52C},telescope=\u{1F52D},pill=\u{1F48A}," +
    "syringe=\u{1F489},test_tube=\u{1F9EA},hourglass=\u{231B}\u{FE0F}," +
    "hourglass_with_flowing_sand=\u{23F3}\u{FE0F},alarm_clock=\u{23F0}\u{FE0F}," +
    "money_with_wings=\u{1F4B8},money_bag=\u{1F4B0},banknote_with_dollar_sign=\u{1F4B5}," +
    "credit_card=\u{1F4B3},gem_stone=\u{1F48E},handbag=\u{1F45C},eyeglasses=\u{1F453}," +
    "school_satchel=\u{1F392},graduation_cap=\u{1F393},crown=\u{1F451},label=\u{1F3F7}\u{FE0F}," +
    "bookmark=\u{1F516},wastebasket=\u{1F5D1}\u{FE0F},"],
  ["symbols", "Hearts and symbols",
    "heavy_black_heart=\u{2764}\u{FE0F},orange_heart=\u{1F9E1},yellow_heart=\u{1F49B}," +
    "green_heart=\u{1F49A},blue_heart=\u{1F499},purple_heart=\u{1F49C},black_heart=\u{1F5A4}," +
    "white_heart=\u{1F90D},brown_heart=\u{1F90E},broken_heart=\u{1F494},sparkling_heart=\u{1F496}," +
    "two_hearts=\u{1F495},hundred_points_symbol=\u{1F4AF},collision_symbol=\u{1F4A5}," +
    "sparkles=\u{2728},dizzy_symbol=\u{1F4AB},speech_balloon=\u{1F4AC},thought_balloon=\u{1F4AD}," +
    "sleeping_symbol=\u{1F4A4},anger_symbol=\u{1F4A2},peace_symbol=\u{262E}\u{FE0F}," +
    "yin_yang=\u{262F}\u{FE0F},black_universal_recycling_symbol=\u{267B}\u{FE0F}," +
    "atom_symbol=\u{269B}\u{FE0F},crystal_ball=\u{1F52E},nazar_amulet=\u{1F9FF}," +
    "diamond_shape_with_a_dot_inside=\u{1F4A0},trident_emblem=\u{1F531},fleur_de_lis=\u{269C}\u{FE0F},"],
  ["marks", "Marks and arrows",
    "white_heavy_check_mark=\u{2705},ballot_box_with_check=\u{2611}\u{FE0F}," +
    "heavy_check_mark=\u{2714}\u{FE0F},cross_mark=\u{274C},negative_squared_cross_mark=\u{274E}," +
    "heavy_plus_sign=\u{2795},heavy_minus_sign=\u{2796},heavy_division_sign=\u{2797}," +
    "black_question_mark_ornament=\u{2753},white_question_mark_ornament=\u{2754}," +
    "heavy_exclamation_mark_symbol=\u{2757}\u{FE0F},white_exclamation_mark_ornament=\u{2755}\u{FE0F}," +
    "double_exclamation_mark=\u{203C}\u{FE0F},exclamation_question_mark=\u{2049}\u{FE0F}," +
    "warning_sign=\u{26A0}\u{FE0F},no_entry=\u{26D4}\u{FE0F},no_entry_sign=\u{1F6AB}," +
    "octagonal_sign=\u{1F6D1},large_red_circle=\u{1F534},large_orange_circle=\u{1F7E0}," +
    "large_yellow_circle=\u{1F7E1},large_green_circle=\u{1F7E2},large_blue_circle=\u{1F535}," +
    "large_purple_circle=\u{1F7E3},medium_black_circle=\u{26AB}\u{FE0F}," +
    "medium_white_circle=\u{26AA}\u{FE0F},large_red_square=\u{1F7E5},large_orange_square=\u{1F7E7}," +
    "large_yellow_square=\u{1F7E8},large_green_square=\u{1F7E9},large_blue_square=\u{1F7E6}," +
    "large_purple_square=\u{1F7EA},black_large_square=\u{2B1B}\u{FE0F}," +
    "white_large_square=\u{2B1C}\u{FE0F},large_orange_diamond=\u{1F536},large_blue_diamond=\u{1F537}," +
    "up_pointing_red_triangle=\u{1F53A},down_pointing_red_triangle=\u{1F53B}," +
    "black_rightwards_arrow=\u{27A1}\u{FE0F},leftwards_black_arrow=\u{2B05}\u{FE0F}," +
    "upwards_black_arrow=\u{2B06}\u{FE0F},downwards_black_arrow=\u{2B07}\u{FE0F}," +
    "north_east_arrow=\u{2197}\u{FE0F},south_east_arrow=\u{2198}\u{FE0F}," +
    "south_west_arrow=\u{2199}\u{FE0F},north_west_arrow=\u{2196}\u{FE0F}," +
    "up_down_arrow=\u{2195}\u{FE0F},left_right_arrow=\u{2194}\u{FE0F}," +
    "anticlockwise_downwards_and_upwards_open_circle_arrows=\u{1F504}," +
    "clockwise_downwards_and_upwards_open_circle_arrows=\u{1F503}," +
    "top_with_upwards_arrow_above=\u{1F51D},squared_new=\u{1F195},squared_free=\u{1F193}," +
    "squared_ok=\u{1F197},squared_up_with_exclamation_mark=\u{1F199},squared_cool=\u{1F192}," +
    "triangular_flag_on_post=\u{1F6A9},chequered_flag=\u{1F3C1},"],
];

//: **Everyday names for emoji** (owner, 2026-10-17: the folded hands "should
//: be both high five and pray"). Search reads the Unicode name, which nobody
//: types; these are the words people do, keyed by the name as the picker shows
//: it. A key that is not a name in the lists above fails
//: `tests/test_icon_picker_aliases.py`.
const ICON_EMOJI_ALIASES = {
  "person with folded hands": "pray prayer please thanks thank you high five namaste hope beg",
  "handshake": "deal agree agreement shake hands partnership",
  "flexed biceps": "strong strength muscle gym flex power",
  "face with tears of joy": "lol laugh laughing funny haha crying laughing",
  "rolling on the floor laughing": "rofl lmao lol laugh funny",
  "loudly crying face": "sob sad cry crying tears upset",
  "crying face": "sad cry tear tears upset",
  "face screaming in fear": "scream scared shocked omg fear horror",
  "smiling face with sunglasses": "cool chill sunglasses awesome",
  "thinking face": "hmm think wondering ponder",
  "winking face": "wink flirt joke",
  "thumbs up sign": "like yes approve good ok agree",
  "thumbs down sign": "dislike no bad disapprove",
  "clapping hands sign": "applause clap bravo well done congrats",
  "waving hand sign": "hello hi bye wave goodbye",
  "ok hand sign": "okay perfect fine good",
  "victory hand": "peace two fingers win",
  "raised hand": "stop wait hand high five",
  "party popper": "celebrate celebration congrats party tada",
  "birthday cake": "birthday cake party dessert",
  "fire": "hot flame lit burn trending",
  "sparkles": "magic shiny new clean glitter",
  "glowing star": "star shine favourite favorite",
  "hundred points symbol": "100 perfect score full marks",
  "electric light bulb": "idea lightbulb light bulb tip",
  "pile of poo": "poop poo crap shit",
  "skull": "dead death danger spooky",
  "rocket": "launch ship fast startup",
  "white heavy check mark": "done tick check complete yes correct",
  "heavy check mark": "done tick check complete yes correct",
  "cross mark": "no wrong x cancel delete",
  "warning sign": "caution alert danger careful",
  "collision symbol": "boom bang crash explosion",
  "eyes": "look see watching looking",
};

//: **Japanese emoticons** (kaomoji; INBOX 904 B81). `[name, text, aliases]`,
//: an array rather than `ICON_EMOJI_SOURCE`'s comma and equals delimited
//: strings, because the faces are made of commas, equals signs and backslashes.
//: Names are what the tile says; the aliases are the words people type.
const ICON_KAOMOJI = [
  ["shrug", "¯\\_(ツ)_/¯", "idk dunno whatever meh who knows"],
  ["table flip", "(╯°□°)╯︵ ┻━┻", "flip table rage angry mad"],
  ["table back", "┬─┬ ノ( ゜-゜ノ)", "put table back calm unflip"],
  ["rage flip", "(ノಠ益ಠ)ノ彡┻━┻", "table flip furious angry mad"],
  ["happy", "(＾▽＾)", "smile glad cheerful pleased"],
  ["big smile", "(≧▽≦)", "happy grin laugh delighted"],
  ["cheer", "\\(^o^)/", "yay hooray happy celebrate arms up"],
  ["yay", "ヽ(>∀<☆)ノ", "happy excited celebrate cheer"],
  ["cute", "(｡◕‿◕｡)", "sweet happy kawaii smile"],
  ["wink", "(^_~)", "joke flirt"],
  ["blush", "(*/ω＼)", "shy embarrassed bashful"],
  ["love", "(♡´▽`♡)", "heart hearts crush adore"],
  ["hug", "(づ｡◕‿‿◕｡)づ", "hugs cuddle embrace comfort"],
  ["crying", "(T_T)", "cry sad tears sob upset"],
  ["sobbing", "(╥﹏╥)", "cry crying sad tears heartbroken"],
  ["sad", "(︶︹︺)", "unhappy down blue upset"],
  ["angry", "(｀Д´)", "mad furious rage upset annoyed"],
  ["disapproval", "ಠ_ಠ", "disapprove stare judging unimpressed look"],
  ["facepalm", "(－‸ლ)", "oh no ugh fail embarrassed"],
  ["surprised", "Σ(°ロ°)", "shock shocked gasp omg wow"],
  ["confused", "(°ー°〃)", "puzzled what huh unsure"],
  ["worried", "(；一_一)", "nervous anxious uneasy concerned"],
  ["nervous", "(°▽°;)", "sweat awkward anxious oops"],
  ["tired", "(´-ω-`)", "sleepy exhausted weary"],
  ["sleeping", "(－_－) zzZ", "sleep sleepy nap zzz tired"],
  ["bow", "m(_ _)m", "sorry thanks thank you apologise respect please"],
  ["salute", "(￣^￣)ゞ", "yes sir ok roger"],
  ["thumbs up", "(b ᵔ▽ᵔ)b", "good great ok approve like"],
  ["wave", "(￣▽￣)ノ", "hello hi bye goodbye"],
  ["pointing", "(☞ﾟヮﾟ)☞", "you this that point"],
  ["dancing", "♪(┌・。・)┌", "dance music party"],
  ["running away", "ε=ε=┏( ・_・)┛", "run flee escape leave"],
  ["lenny face", "( ͡° ͜ʖ ͡°)", "lenny smirk cheeky"],
  ["cool", "(⌐■_■)", "sunglasses shades chill"],
  ["bear", "ʕ•ᴥ•ʔ", "animal teddy cute"],
  ["cat", "(=^･ω･^=)", "kitty kitten neko animal"],
  ["magic", "(ﾉ◕ヮ◕)ﾉ*:･ﾟ✧", "sparkle sparkles wand wizard"],
];

//: This file's only mutable state, one object (the global-scope ratchet): the
//: emoji groups, parsed once on first open as `[{key, label, items: [{name, glyph}]}]`,
//: the icon groups likewise, and the open panel.
const iconPickerState = { emojiGroups: null, phGroups: null, open: null };

//: The text a search reads for one tile: its name, its everyday aliases and its
//: group, lower case.
function iconPickerHay(choice, groupLabel) {
  const aliases = choice.aliases || ICON_EMOJI_ALIASES[choice.name] || "";
  return `${choice.name} ${aliases} ${groupLabel}`.toLowerCase();
}

function iconPickerEmojiGroups() {
  if (!iconPickerState.emojiGroups) {
    iconPickerState.emojiGroups = ICON_EMOJI_SOURCE.map(([key, label, source]) => ({
      key,
      label,
      items: source.split(",").filter(Boolean).map((pair) => {
        const at = pair.indexOf("=");
        return { kind: "emoji", value: pair.slice(at + 1), name: pair.slice(0, at).replace(/_/g, " ") };
      }),
    }));
    //: Last: a long face is a wide tile (`wide`), and a pick is inserted as text.
    iconPickerState.emojiGroups.push({
      key: "kaomoji",
      label: "Japanese emoticons",
      items: ICON_KAOMOJI.map(([name, value, aliases]) => ({ kind: "emoji", value, name, aliases, wide: true })),
    });
  }
  return iconPickerState.emojiGroups;
}

//: **Phosphor's groups, by what a name says** (the font carries no
//: categories). First match wins; the rest are "More icons". Ordered so the
//: groups a map or a note reaches for most come first.
const ICON_PH_GROUPS = [
  ["marks", "Marks and shapes", /^(check|x-|x$|warning|question|info|seal|star|heart|flag|target|circle|square|diamond|triangle|hexagon|octagon|plus|minus|asterisk|crown|medal|trophy|lightbulb|sparkle)/],
  ["arrows", "Arrows", /^(arrow|caret|arrows|trend)/],
  ["people", "People", /(user|person|users|baby|hand|smiley|identification|student|chalkboard-teacher|detective)/],
  ["work", "Work and writing", /(file|folder|note|notebook|book|pen|pencil|paper|clipboard|article|text-|list|quotes|briefcase|kanban|calendar|clock|timer|hourglass|alarm|chart|graph|table|database|presentation|funnel|tag)/],
  ["talk", "Talk and media", /(chat|envelope|phone|bell|megaphone|paper-plane|broadcast|microphone|speaker|music|headphones|camera|video|film|image|play|pause|television)/],
  ["places", "Places and travel", /(map|globe|house|building|airplane|car|bus|train|bicycle|compass|navigation|signpost|tent|mountains|island|bridge|storefront|bank|hospital|church|school)/],
  ["nature", "Nature", /(tree|leaf|flower|plant|sun|moon|cloud|snow|drop|fire|flame|lightning|mountain|bug|cat|dog|fish|bird|paw|butterfly|cactus|plant|wave|rainbow|thermometer|wind)/],
  ["things", "Things and tools", /(key|lock|gear|wrench|hammer|gift|desktop|laptop|device|cpu|robot|rocket|lamp|coffee|cooking|fork|bag|basket|shopping|money|coin|credit|wallet|puzzle|game|dice|palette|paint|scissors|magnifying|binoculars|flask|atom|dna|pill|first-aid)/],
];

//: The vendored font's glyph names, off its own stylesheet's rules.
function iconPickerPhosphorNames() {
  const names = [];
  for (const sheet of document.styleSheets) {
    if (!/\/vendor\/phosphor\//.test(sheet.href || "")) continue;
    let rules;
    try {
      rules = sheet.cssRules;
    } catch {
      continue;
    }
    for (const rule of rules) {
      const match = /^\.ph\.ph-([a-z0-9-]+)::?before$/.exec(rule.selectorText || "");
      if (match) names.push(match[1]);
    }
  }
  return names;
}

function iconPickerIconGroups() {
  if (!iconPickerState.phGroups) {
    const groups = ICON_PH_GROUPS.map(([key, label]) => ({ key, label, items: [] }));
    const more = { key: "more", label: "More icons", items: [] };
    for (const name of iconPickerPhosphorNames()) {
      const at = ICON_PH_GROUPS.findIndex(([, , re]) => re.test(name));
      (at === -1 ? more : groups[at]).items.push({ kind: "icon", value: name, name: name.replace(/-/g, " ") });
    }
    iconPickerState.phGroups = [...groups.filter((g) => g.items.length), ...(more.items.length ? [more] : [])];
  }
  return iconPickerState.phGroups;
}

//: Recent picks, newest first, on this device (`prefs`, wrapped).
const ICON_PICKER_RECENT_KEY = "icon-picker-recent";
const ICON_PICKER_RECENT_MAX = 20;

function iconPickerRecent() {
  const list = prefs.json(ICON_PICKER_RECENT_KEY, []);
  return list.filter((r) => r && (r.kind === "emoji" || r.kind === "icon") && typeof r.value === "string").slice(0, ICON_PICKER_RECENT_MAX);
}

function iconPickerRemember(choice) {
  const list = [choice, ...iconPickerRecent().filter((r) => !(r.kind === choice.kind && r.value === choice.value))];
  try {
    prefs.set(ICON_PICKER_RECENT_KEY, JSON.stringify(list.slice(0, ICON_PICKER_RECENT_MAX)));
  } catch {
    // Private mode: nothing remembered, the panel still works.
  }
}

//: How many tiles a group draws while browsing, before its "Show all".
const ICON_PICKER_PAGE = 48;

//: What a choice is as text, for a drop into a text box or an insert: an
//: emoji is itself, an icon the token the reading view draws (decision 46).
function iconPickerText(choice) {
  return choice.kind === "emoji" ? choice.value : `:ph-${choice.value}:`;
}

//: A tile's glyph element: the emoji as text, the icon as Phosphor's `<i>`.
function iconPickerGlyph(choice) {
  const glyph = document.createElement(choice.kind === "emoji" ? "span" : "i");
  if (choice.kind === "emoji") {
    glyph.className = choice.wide ? "icon-picker-emoji icon-picker-kaomoji" : "icon-picker-emoji";
    glyph.textContent = choice.value;
  } else {
    glyph.className = `ph ph-${choice.value}`;
  }
  glyph.setAttribute("aria-hidden", "true");
  return glyph;
}

//: The choice being dragged right now: `dragover` cannot read the data a
//: drag carries, so a drop target that wants to say "copy" asks this.
window.iconPickerDragging = null;

function closeIconPicker() {
  iconPickerState.open?.close();
}

//: **Opens the picker** beside `anchor`. `onPick({kind, value})` is called
//: with the chosen glyph: `kind` is `emoji` or `icon`, `value` the glyph or
//: the Phosphor name. `modes` limits the two tabs; `keepOpen` leaves the
//: panel up after a pick (a board placing several stickers); `title` heads it.
//: Returns `{close}`.
function openIconPicker({ anchor = null, onPick = null, modes = ["emoji", "icon"], mode = null, keepOpen = false, title = "Emoji and icons" } = {}) {
  closeIconPicker();
  const kinds = modes.filter((m) => m === "emoji" || m === "icon");
  let current = kinds.includes(mode) ? mode : kinds[0] || "emoji";
  let query = "";
  const expanded = new Set();
  const returnFocus = document.activeElement;

  const panel = document.createElement("div");
  panel.className = "help-popover icon-picker";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", title);
  const close = () => {
    if (!panel.isConnected) return;
    document.removeEventListener("pointerdown", outside, true);
    panel.remove();
    if (iconPickerState.open?.panel === panel) iconPickerState.open = null;
  };
  //: Focus goes back to what opened it, or, when that sat in a menu that has
  //: closed since, to the menu's own button: never to the page body.
  const closeAndReturn = () => {
    close();
    let back = returnFocus?.isConnected && returnFocus !== document.body ? returnFocus : anchor;
    if (!back?.isConnected) back = null;
    if (back && !back.getClientRects().length) {
      let toggle = null;
      for (let el = back.parentElement; el && !toggle; el = el.parentElement) {
        const named = el.id ? document.querySelector(`[aria-controls="${CSS.escape(el.id)}"]`) : null;
        if (named?.getClientRects().length) toggle = named;
      }
      back = toggle;
    }
    back?.focus({ preventScroll: true });
  };
  const head = dialogHead(title, closeAndReturn);

  const field = document.createElement("div");
  field.className = "search-field";
  const lens = document.createElement("i");
  lens.className = "ph ph-magnifying-glass search-field-icon";
  lens.setAttribute("aria-hidden", "true");
  const search = document.createElement("input");
  search.type = "search";
  search.className = "search-field-input";
  search.autocomplete = "off";
  search.placeholder = "Search emoji and icons";
  search.setAttribute("aria-label", "Search emoji and icons");
  field.append(lens, search);

  //: **The kind is a tab strip under the head, never a pill** (INBOX 715, the
  //: owner: "i dont like pills like that in popups"): DESIGN.md's "a popup
  //: chooses a kind" row, the arrows and Home and End walking it.
  const tabs = document.createElement("div");
  tabs.className = "tabs-line popup-kinds icon-picker-modes";
  tabs.setAttribute("role", "tablist");
  tabs.setAttribute("aria-label", "Emoji or icons");
  for (const [kind, label] of [["emoji", "Emoji"], ["icon", "Icons"]]) {
    if (!kinds.includes(kind)) continue;
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "tab");
    b.dataset.mode = kind;
    b.textContent = label;
    b.addEventListener("click", () => {
      current = kind;
      draw();
      search.focus({ preventScroll: true });
    });
    tabs.appendChild(b);
  }
  tabs.addEventListener("keydown", (e) => {
    const all = [...tabs.children];
    const at = all.findIndex((b) => b.dataset.mode === current);
    const to = { ArrowRight: at + 1, ArrowLeft: at - 1, Home: 0, End: all.length - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    const b = all[(to + all.length) % all.length];
    current = b.dataset.mode;
    draw();
    b.focus();
  });

  const list = document.createElement("div");
  list.className = "icon-picker-list";
  list.setAttribute("role", "listbox");
  list.setAttribute("aria-label", title);
  list.tabIndex = 0;
  const status = document.createElement("p");
  status.className = "muted icon-picker-hint";
  status.setAttribute("aria-live", "polite");

  panel.append(head);
  if (tabs.children.length > 1) panel.append(tabs);
  panel.append(field, list, status);

  let tiles = [];
  let active = -1;
  let idSeq = 0;
  const setActive = (at, { scroll = true } = {}) => {
    if (!tiles.length) return;
    active = Math.max(0, Math.min(tiles.length - 1, at));
    tiles.forEach((t, i) => t.classList.toggle("active", i === active));
    const tile = tiles[active];
    list.setAttribute("aria-activedescendant", tile.id);
    status.textContent = tile.dataset.name;
    if (scroll) tile.scrollIntoView({ block: "nearest" });
  };
  const pick = (choice) => {
    iconPickerRemember(choice);
    if (!keepOpen) closeAndReturn();
    onPick?.(choice);
  };
  const tile = (choice) => {
    const el = document.createElement("div");
    el.className = "icon-picker-tile";
    el.id = `icon-picker-tile-${++idSeq}`;
    el.setAttribute("role", "option");
    el.setAttribute("aria-label", choice.name);
    el.title = choice.name;
    el.dataset.name = choice.name;
    el.draggable = true;
    el._choice = choice;
    if (choice.wide) el.classList.add("icon-picker-tile-wide");
    el.appendChild(iconPickerGlyph(choice));
    return el;
  };
  const groupHead = (text) => {
    const h = document.createElement("div");
    h.className = "icon-picker-group";
    h.setAttribute("role", "presentation");
    h.textContent = text;
    return h;
  };
  const grid = () => {
    const g = document.createElement("div");
    g.className = "icon-picker-grid";
    g.setAttribute("role", "presentation");
    return g;
  };
  const draw = () => {
    for (const b of tabs.children) {
      b.setAttribute("aria-selected", String(b.dataset.mode === current));
      b.tabIndex = b.dataset.mode === current ? 0 : -1;
    }
    const groups = current === "emoji" ? iconPickerEmojiGroups() : iconPickerIconGroups();
    const q = query.trim().toLowerCase();
    const parts = [];
    tiles = [];
    const addGroup = (label, items, key) => {
      if (!items.length) return;
      parts.push(groupHead(label));
      const g = grid();
      const shown = q || expanded.has(key) ? items : items.slice(0, ICON_PICKER_PAGE);
      for (const choice of shown) {
        const t = tile(choice);
        tiles.push(t);
        g.appendChild(t);
      }
      parts.push(g);
      if (shown.length < items.length) {
        const more = smallButton(`ph:caret-down Show all ${items.length}`, `Show every one in ${label}`, () => {
          expanded.add(key);
          draw();
        });
        more.classList.add("icon-picker-more");
        parts.push(more);
      }
    };
    if (q) {
      //: Every word must match the name or the group, so "red heart" finds
      //: the heart and not every red thing.
      const words = q.split(/\s+/).filter(Boolean);
      const found = [];
      for (const group of groups) {
        for (const choice of group.items) {
          const hay = iconPickerHay(choice, group.label);
          if (words.every((w) => hay.includes(w))) found.push(choice);
        }
      }
      found.sort((a, b) => (a.name.startsWith(words[0]) ? 0 : 1) - (b.name.startsWith(words[0]) ? 0 : 1));
      addGroup(`${found.length} found`, found.slice(0, 240), "found");
      if (!found.length) {
        const none = document.createElement("p");
        none.className = "muted icon-picker-empty";
        none.textContent = current === "emoji" ? "No emoji by that name. Try Icons." : "No icon by that name. Try Emoji.";
        parts.push(none);
      }
    } else {
      const recent = iconPickerRecent().filter((r) => r.kind === current).map((r) => {
        const all = groups.flatMap((g) => g.items);
        return all.find((c) => c.value === r.value) || { ...r, name: r.value.replace(/-/g, " ") };
      });
      addGroup("Recent", recent, "recent");
      for (const group of groups) addGroup(group.label, group.items, group.key);
    }
    list.replaceChildren(...parts);
    active = -1;
    list.removeAttribute("aria-activedescendant");
    status.textContent = tiles.length ? "Arrows to move, Enter to choose, or drag one where it goes." : "";
  };

  //: The number of tiles in one row, read off the layout rather than assumed.
  const rowLength = () => {
    const first = tiles[0];
    if (!first) return 1;
    const top = first.offsetTop;
    let n = 0;
    while (n < tiles.length && tiles[n].offsetTop === top && tiles[n].parentElement === first.parentElement) n += 1;
    return Math.max(1, n);
  };

  search.addEventListener("input", () => {
    query = search.value;
    draw();
  });
  search.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" && tiles.length) {
      event.preventDefault();
      list.focus({ preventScroll: true });
      setActive(0);
    } else if (event.key === "Enter" && tiles.length) {
      event.preventDefault();
      pick(tiles[active >= 0 ? active : 0]._choice);
    }
  });
  list.addEventListener("focus", () => {
    if (active < 0) setActive(0, { scroll: false });
  });
  list.addEventListener("keydown", (event) => {
    const across = rowLength();
    const moves = { ArrowRight: 1, ArrowLeft: -1, ArrowDown: across, ArrowUp: -across };
    if (event.key in moves) {
      event.preventDefault();
      if (event.key === "ArrowUp" && active < across) {
        search.focus({ preventScroll: true });
        return;
      }
      setActive(active + moves[event.key]);
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      setActive(event.key === "Home" ? 0 : tiles.length - 1);
    } else if ((event.key === "Enter" || event.key === " ") && active >= 0) {
      event.preventDefault();
      pick(tiles[active]._choice);
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      search.focus({ preventScroll: true });
    }
  });
  list.addEventListener("click", (event) => {
    const t = event.target.closest(".icon-picker-tile");
    if (t) pick(t._choice);
  });
  list.addEventListener("dragstart", (event) => {
    const t = event.target.closest(".icon-picker-tile");
    if (!t) return;
    const choice = t._choice;
    event.dataTransfer.setData("text/plain", iconPickerText(choice));
    event.dataTransfer.setData("application/x-memorymap-icon", JSON.stringify({ kind: choice.kind, value: choice.value }));
    event.dataTransfer.effectAllowed = "copy";
    window.iconPickerDragging = choice;
    iconPickerRemember(choice);
  });
  list.addEventListener("dragend", () => {
    window.iconPickerDragging = null;
  });
  //: **No key leaves the panel.** It is a dialog: an Enter that picked a
  //: tile must not go on to the canvas behind it, where Enter adds a topic
  //: (measured: one pick by Enter on a map made two empty topics).
  panel.addEventListener("keydown", (event) => {
    event.stopPropagation();
    if (event.key === "Escape") {
      event.preventDefault();
      closeAndReturn();
    }
  });
  //: Outside a press closes it, unless a drag from it is under way.
  const outside = (event) => {
    if (panel.contains(event.target) || anchor?.contains?.(event.target) || window.iconPickerDragging) return;
    close();
  };
  document.addEventListener("pointerdown", outside, true);

  draw();
  document.body.appendChild(panel);
  //: An anchor that is not on screen (inside a menu that closed as it was
  //: pressed) has no place to hang from: the middle of the window instead.
  const rect = anchor?.getBoundingClientRect?.();
  if (rect && (rect.width || rect.height)) placeHelpPopover(panel, anchor);
  else panel.classList.add("icon-picker-centred");
  search.focus({ preventScroll: true });
  //: **The focus stays put while the panel settles.** On a first use an
  //: editor behind it can mount and take the focus a frame later (measured:
  //: the note composer's CodeMirror, 127ms after the search field had it, so
  //: the next letters typed went into the note). For a moment after opening,
  //: focus that lands outside the open panel comes back; any press outside
  //: closes the panel first, so nobody's own move is undone.
  const openedAt = performance.now();
  const keepFocus = (event) => {
    if (!panel.isConnected || performance.now() - openedAt > 800) {
      document.removeEventListener("focusin", keepFocus, true);
      return;
    }
    if (!panel.contains(event.target)) search.focus({ preventScroll: true });
  };
  document.addEventListener("focusin", keepFocus, true);
  iconPickerState.open = { panel, close };
  return { close, panel };
}
