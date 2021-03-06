import configparser
import ctypes
import mmap
import msvcrt
import multiprocessing as mp
import os
import random
import time
import io

import bot_input_struct as bi
import bot_manager
import game_data_struct as gd
import rlbot_exception

from conversions.server_converter import ServerConverter


PARTICPANT_CONFIGURATION_HEADER = 'Participant Configuration'
PARTICPANT_BOT_KEY_PREFIX = 'participant_is_bot_'
PARTICPANT_RLBOT_KEY_PREFIX = 'participant_is_rlbot_controlled_'
PARTICPANT_CONFIG_KEY_PREFIX = 'participant_config_'
PARTICPANT_BOT_SKILL_KEY_PREFIX = 'participant_bot_skill_'
PARTICPANT_TEAM_PREFIX = 'participant_team_'
RLBOT_CONFIG_FILE = 'rlbot.cfg'
RLBOT_CONFIGURATION_HEADER = 'RLBot Configuration'
INPUT_SHARED_MEMORY_TAG = 'Local\\RLBotInput'
BOT_CONFIG_LOADOUT_HEADER = 'Participant Loadout'
BOT_CONFIG_MODULE_HEADER = 'Bot Location'
USER_CONFIGURATION_HEADER = 'User Info'


try:
    import config
    server_manager = ServerConverter(config.UPLOAD_SERVER, True, True, True, username='Sciguymjm')
except ImportError:
    server_manager = ServerConverter('', False, False, False)
    print('config.py not present, cannot upload replays to collective server')
    print('Check Discord server for information')


if server_manager.error:
    server_manager.warn_server('unable to connect to server')


def get_bot_config_file_list(botCount, config):
    config_file_list = []
    for i in range(botCount):
        config_file_list.append(config.get(PARTICPANT_CONFIGURATION_HEADER, PARTICPANT_CONFIG_KEY_PREFIX + str(i)))
    return config_file_list


# Cut off at 31 characters and handle duplicates
def get_sanitized_bot_name(dict, name):
    if name not in dict:
        new_name = name[:31]  # Make sure name does not exceed 31 characters
        dict[name] = 1
    else:
        count = dict[name]
        new_name = name[:27] + "(" + str(count + 1) + ")"  # Truncate at 27 because we can have up to '(10)' appended
        dict[name] = count + 1

    return new_name


def run_agent(terminate_event, callback_event, config_file, name, team, index, module_name, game_name, save_data, server_uploader):
    bm = bot_manager.BotManager(terminate_event, callback_event, config_file, name, team,
                                index, module_name, game_name, save_data, server_uploader)
    bm.run()


if __name__ == '__main__':
    # Set up RLBot.cfg
    framework_config = configparser.RawConfigParser()
    framework_config.read(RLBOT_CONFIG_FILE)

    # Open anonymous shared memory for entire GameInputPacket and map buffer
    buff = mmap.mmap(-1, ctypes.sizeof(bi.GameInputPacket), INPUT_SHARED_MEMORY_TAG)
    gameInputPacket = bi.GameInputPacket.from_buffer(buff)

    # Determine number of participants
    num_participants = framework_config.getint(RLBOT_CONFIGURATION_HEADER, 'num_participants')

    try:
        server_manager.set_player_username(framework_config.get(USER_CONFIGURATION_HEADER, 'username'))
    except Exception as e:
        print('username not set in config', e)
        print('using default username')

    # Retrieve bot config files
    participant_configs = get_bot_config_file_list(num_participants, framework_config)

    # Create empty lists
    bot_names = []
    bot_teams = []
    bot_modules = []
    processes = []
    callbacks = []
    config_files = []
    name_dict = dict()

    save_data = True
    save_path = os.getcwd() + '/training/replays'
    game_name = str(int(round(time.time() * 1000))) + '-' + str(random.randint(0, 1000))
    if save_data:
        print(save_path)
        if not os.path.exists(save_path):
            print(os.path.dirname(save_path) + ' does not exist creating')
            os.makedirs(save_path)
        if not os.path.exists(save_path + '\\' + game_name):
            os.makedirs(save_path + '\\' + game_name)
        print('gameName: ' + game_name + 'in ' + save_path)

    gameInputPacket.iNumPlayers = num_participants
    server_manager.download_files()


    num_team_0 = 0
    # Set configuration values for bots and store name and team
    for i in range(num_participants):
        bot_config = configparser.RawConfigParser()
        if server_manager.download_config:
            if 'saltie' in os.path.basename(participant_configs[i]):
                bot_config._read(io.StringIO(server_manager.config_response.json()['content']), 'saltie.cfg')
            else:
                bot_config.read(participant_configs[i])
        else:
            bot_config.read(participant_configs[i])

        gameInputPacket.sPlayerConfiguration[i].bBot = framework_config.getboolean(PARTICPANT_CONFIGURATION_HEADER,
                                                                                   PARTICPANT_BOT_KEY_PREFIX + str(i))
        gameInputPacket.sPlayerConfiguration[i].bRLBotControlled = framework_config.getboolean(
            PARTICPANT_CONFIGURATION_HEADER,
            PARTICPANT_RLBOT_KEY_PREFIX + str(i))
        gameInputPacket.sPlayerConfiguration[i].fBotSkill = framework_config.getfloat(PARTICPANT_CONFIGURATION_HEADER,
                                                                                      PARTICPANT_BOT_SKILL_KEY_PREFIX
                                                                                      + str(i))
        gameInputPacket.sPlayerConfiguration[i].iPlayerIndex = i
        gameInputPacket.sPlayerConfiguration[i].wName = get_sanitized_bot_name(name_dict,
                                                                               bot_config.get(BOT_CONFIG_LOADOUT_HEADER,
                                                                                              'name'))
        gameInputPacket.sPlayerConfiguration[i].ucTeam = framework_config.getint(PARTICPANT_CONFIGURATION_HEADER,
                                                                                 PARTICPANT_TEAM_PREFIX + str(i))
        if gameInputPacket.sPlayerConfiguration[i].ucTeam == 0:
            num_team_0 += 1
        gameInputPacket.sPlayerConfiguration[i].ucTeamColorID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                  'team_color_id')
        gameInputPacket.sPlayerConfiguration[i].ucCustomColorID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                    'custom_color_id')
        gameInputPacket.sPlayerConfiguration[i].iCarID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'car_id')
        gameInputPacket.sPlayerConfiguration[i].iDecalID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'decal_id')
        gameInputPacket.sPlayerConfiguration[i].iWheelsID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'wheels_id')
        gameInputPacket.sPlayerConfiguration[i].iBoostID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'boost_id')
        gameInputPacket.sPlayerConfiguration[i].iAntennaID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'antenna_id')
        gameInputPacket.sPlayerConfiguration[i].iHatID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'hat_id')
        gameInputPacket.sPlayerConfiguration[i].iPaintFinish1ID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                    'paint_finish_1_id')
        gameInputPacket.sPlayerConfiguration[i].iPaintFinish2ID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                    'paint_finish_2_id')
        gameInputPacket.sPlayerConfiguration[i].iEngineAudioID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                   'engine_audio_id')
        gameInputPacket.sPlayerConfiguration[i].iTrailsID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER, 'trails_id')
        gameInputPacket.sPlayerConfiguration[i].iGoalExplosionID = bot_config.getint(BOT_CONFIG_LOADOUT_HEADER,
                                                                                     'goal_explosion_id')
        config_files.append(bot_config)
        bot_names.append(bot_config.get(BOT_CONFIG_LOADOUT_HEADER, 'name'))
        bot_teams.append(framework_config.getint(PARTICPANT_CONFIGURATION_HEADER, PARTICPANT_TEAM_PREFIX + str(i)))
        if gameInputPacket.sPlayerConfiguration[i].bRLBotControlled:
            bot_modules.append(bot_config.get(BOT_CONFIG_MODULE_HEADER, 'agent_module'))
        else:
            bot_modules.append('NO_MODULE_FOR_PARTICIPANT')

    server_manager.set_player_amount(num_participants, num_team_0)

    # Create Quit event
    quit_event = mp.Event()

    # Launch processes
    for i in range(num_participants):
        if gameInputPacket.sPlayerConfiguration[i].bRLBotControlled:
            callback = mp.Event()
            callbacks.append(callback)
            process = mp.Process(target=run_agent, args=(
                quit_event, callback, config_files[i], str(gameInputPacket.sPlayerConfiguration[i].wName),
                bot_teams[i], i, bot_modules[i], save_path + '\\' + game_name, save_data, server_manager))
            process.start()

    print("Successfully configured bots. Setting flag for injected dll.")
    gameInputPacket.bStartMatch = True

    # Wait 100 milliseconds then check for an error code
    time.sleep(0.1)
    game_data_shared_memory = mmap.mmap(-1, ctypes.sizeof(gd.GameTickPacketWithLock),
                                        bot_manager.OUTPUT_SHARED_MEMORY_TAG)
    bot_output = gd.GameTickPacketWithLock.from_buffer(game_data_shared_memory)
    if not bot_output.iLastError == 0:
        # Terminate all process and then raise an exception
        quit_event.set()
        terminated = False
        while not terminated:
            terminated = True
            for callback in callbacks:
                if not callback.is_set():
                    terminated = False
        raise rlbot_exception.RLBotException().raise_exception_from_error_code(bot_output.iLastError)

    print("Press any character to exit")
    msvcrt.getch()

    print("Shutting Down")
    quit_event.set()
    # Wait for all processes to terminate before terminating main process
    terminated = False
    while not terminated:
        terminated = True
        for callback in callbacks:
            if not callback.is_set():
                terminated = False
