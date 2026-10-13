"""Steam identifiers shared by deployment and supported Workshop publication."""

GAME_STEAM_APP_IDS = {
    "victoria3": "529340",
    "stellaris": "281990",
    "hoi4": "394360",
    "eu4": "236850",
    "ck3": "1158310",
    "eu5": "3450310",
}

GAME_NAMES = {
    "victoria3": "Victoria 3", "stellaris": "Stellaris", "hoi4": "Hearts of Iron IV",
    "eu4": "Europa Universalis IV", "ck3": "Crusader Kings III", "eu5": "Europa Universalis V",
}


def publication_game_options(game_ids):
    return [{"game_id": game_id, "app_id": int(app_id), "name": GAME_NAMES[game_id]}
            for game_id, app_id in GAME_STEAM_APP_IDS.items() if game_id in game_ids]
