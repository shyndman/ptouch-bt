from enum import IntEnum


class LabelColor(IntEnum):
    WHITE = 1
    OTHERS = 2
    CLEAR = 3
    RED = 4
    BLUE = 5
    YELLOW = 6
    GREEN = 7
    BLACK = 8
    CLEAR_WHITE = 9
    GOLD = 10
    GOLD_PREMIUM = 11
    SILVER_PREMIUM = 12
    OTHERS_PREMIUM = 13
    OTHERS_MASKING = 14
    LIGHTBLUE_SATIN = 15
    MINT_SATIN = 16
    SILVER_SATIN = 17
    MATTE_WHITE = 32
    MATTE_CLEAR = 33
    MATTE_SILVER = 34
    SATIN_GOLD = 35
    SATIN_SILVER = 36
    PASTEL_PURPLE = 37
    BLUE_WHITE = 48
    RED_WHITE = 49
    FLUORESCENT_ORANGE = 64
    FLUORESCENT_YELLOW = 65
    BERRY_PINK = 80
    LIGHT_GRAY = 81
    LIME_GREEN = 82
    NAVY_BLUE = 83
    WINE_RED = 84
    FABRIC_YELLOW = 96
    FABRIC_PINK = 97
    FABRIC_BLUE = 98
    TUBE_WHITE = 112
    SELF_WHITE = 128
    FLEXIBLE_WHITE = 144
    FLEXIBLE_YELLOW = 145
    CLEANING = 240
    STENCIL = 241
    UNSUPPORT = 255


def label_color(value):
    try:
        return LabelColor(value)
    except ValueError:
        return LabelColor.UNSUPPORT


def label_color_name(value):
    return label_color(value).name.lower().replace("_", "-")
