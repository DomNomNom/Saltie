import itertools

import numpy as np
import tensorflow as tf

from modelHelpers.actions.action_handler import ActionHandler, ActionMap
from modelHelpers.actions.split_action_handler import SplitActionHandler


COMBO = 'combo'

super_split_scheme = [[('throttle', (-1, 1.5, .5)), ('steer', (-1, 1.5, .5)),
                       ('yaw', (-1, 1.5, .5)), ('pitch', (-1, 1.5, .5)), ('roll', (-1, 1.5, .5))],
                      [('jump', (0, 2, 1)), ('boost', (0, 2, 1)), ('handbrake', (0, 2, 1))],
                      []]






class DynamicActionHandler(SplitActionHandler):
    """Very dynamic for controls and splitting.
        Assumes everything is in tensorflow
    """

    control_names_index_map = {}
    # rules, tuples mean they take the same spot
    ranged_actions = []
    action_list_names = []
    action_name_index_map = {}
    combo_name_index_map = {}
    action_sizes = []
    combo_action_sizes = []
    combo_list = []
    button_combo = []
    combo_name_list = []
    dodge_suppressor_list = [['jump'], ['steer', 'pitch', 'roll', 'yaw']]
    should_suppress_dodge = False

    def __init__(self, control_scheme):
        self.control_scheme = control_scheme
        super().__init__()

    def reset(self):
        super().reset()
        self.control_names_index_map = {}
        self.ranged_actions = []
        self.action_list_names = []
        self.action_name_index_map = {}
        self.combo_name_index_map = {}
        self.action_sizes = []
        self.combo_action_sizes = []
        self.actions = []
        self.combo_list = []
        self.button_combo = []
        self.combo_name_list = []

    def create_range_action(self, item):
        action_data = np.arange(*item[1])
        return action_data

    def create_actions(self):
        self.reset()

        for i, item in enumerate(self.control_names):
            self.control_names_index_map[item] = i

        ranges = self.control_scheme[0]
        combo_scheme = self.control_scheme[1]
        copies = self.control_scheme[2]

        for item in ranges:
            action = self.create_range_action(item)
            self.action_sizes.append(len(action))
            self.action_name_index_map[item[0]] = len(self.action_list_names)
            self.action_list_names.append(item[0])
            self.actions.append(action)

        self.ranged_actions = list(self.actions)

        for item in combo_scheme:
            action = self.create_range_action(item)
            self.combo_name_list.append(item[0])
            self.action_name_index_map[item[0]] = COMBO
            self.combo_name_index_map[item[0]] = len(self.combo_list)
            self.combo_list.append(action)
            self.combo_action_sizes.append(len(action))
            if item[0] == 'dodge':
                self.should_suppress_dodge = True
        self.button_combo = list(itertools.product(*self.combo_list))
        self.action_sizes.append(len(self.button_combo))
        self.action_name_index_map[COMBO] = len(self.action_list_names)
        self.action_list_names.append(COMBO)
        self.actions.append(self.button_combo)

        for item in copies:
            self.action_name_index_map[item[0]] = self.action_name_index_map[item[1]]
        return self.actions

    def create_action_map(self):
        return ActionMap(self.button_combo)

    def create_controller_from_selection(self, action_selection):
        if len(action_selection) != len(self.actions):
            raise Exception('Invalid action selection size')

        combo_index = self.action_name_index_map[COMBO]
        controller_output = []
        for control in self.control_names:
            index = self.action_name_index_map[control]
            if index == COMBO:
                true_index = self.combo_name_index_map[control]
                controller_output.append(self.actions[combo_index][action_selection[combo_index]][true_index])
                continue
            controller_output.append(self.actions[index][action_selection[index]])

        # print(controller_output)
        return controller_output

    def create_tensorflow_controller_from_selection(self, action_selection, batch_size=1, should_stack=True):
        controller_output = []

        ranged_actions = []
        combo_actions = tf.constant(np.transpose(np.array(self.button_combo)))
        action_selection = tf.cast(action_selection, tf.int32)

        # handle ranged actions
        multiplier = tf.constant([int(batch_size), 1])
        for ranged_action in self.ranged_actions:
            action = tf.constant(np.array(ranged_action))
            if batch_size > 1:
                expanded_action = tf.expand_dims(action, 0)
                action = tf.tile(expanded_action, multiplier)
            ranged_actions.append(action)

        # handle combo buttons
        if batch_size > 1:
            multiplier = tf.constant([1, int(batch_size), 1])
            combo_actions = tf.tile(tf.expand_dims(combo_actions, 1), multiplier)
            indexer = tf.constant(np.arange(0, batch_size, 1), dtype=tf.int32)
        else:
            indexer = tf.constant(1, dtype=tf.int32)

        combo_index = self.action_name_index_map[COMBO]
        # actually decoding the controls now the startup is done

        controls = self.control_names

        for control in controls:
            index = self.action_name_index_map[control]
            if index == COMBO:
                true_index = self.combo_name_index_map[control]
                single_element = combo_actions[true_index]
                controller_output.append(
                    tf.gather_nd(single_element, tf.stack([indexer, action_selection[combo_index]], axis=1)))
                continue
            ranged_action = ranged_actions[index]
            selection = action_selection[index]
            output = tf.gather_nd(ranged_action, tf.stack([indexer, selection], axis=1))
            controller_output.append(output)

        # make sure everything is the same type
        controller_output = [tf.cast(option, tf.float32) for option in controller_output]

        if should_stack:
            return tf.stack(controller_output, axis=1)
        return controller_output

    def round_action(self, input, action_size):
        rounded_amount = float(action_size // 2)
        return float(round(rounded_amount * input)) / rounded_amount

    def _create_combo_index(self, real_action, combo_list):
        return self.action_map.get_key(combo_list)

    def create_action_index(self, real_action):
        combo_list = []
        indexes = []
        for i in range(len(self.combo_list)):
            combo_list.append([])
        for i in range(len(self.actions)):
            indexes.append(None)
        for i, control in enumerate(self.control_names):
            if i >= len(real_action):
                continue
            real_control = real_action[i]
            action_index = self.action_name_index_map[control]

            if action_index == COMBO:
                real_index = self.combo_name_index_map[control]
                action_size = self.combo_action_sizes[real_index]
                bucketed_control = self.round_action(real_control, action_size)
                combo_list[real_index] = bucketed_control
            else:
                if indexes[action_index] is None:
                    indexes[action_index] = (self._find_closet_real_number(real_control))

        indexes[self.action_name_index_map[COMBO]] = self._create_combo_index(real_action, combo_list)

        return indexes

    def _create_combo_index_graph(self, combo_list, real_action=None):
        binary_combo_index = tf.constant(0.0)
        for i, name in enumerate(reversed(self.combo_name_list)):
            true_index = self.combo_name_index_map[name]
            powed = tf.constant(pow(2, i), dtype=tf.float32)
            action_taken = combo_list[true_index]
            if self.combo_action_sizes[true_index] > 2:
                combo_list = self.combo_list[true_index]
                new_range = self.combo_action_sizes[true_index] // 2 + 1
                for j in range(new_range):
                    powed = tf.constant(pow(2, i + (new_range - 1 - j)), dtype=tf.float32)
                    binary_combo_index += powed * (tf.cast(
                        tf.equal(action_taken, combo_list[len(combo_list) - 1 - j]), tf.float32))
            else:
                binary_combo_index += powed * tf.cast(action_taken, tf.float32)
        return binary_combo_index

    def create_action_indexes_graph(self, real_action, batch_size=None):
        indexes = []
        combo_list = []
        for i in range(len(self.combo_name_list)):
            combo_list.append(None)
        for i in range(len(self.actions)):
            indexes.append(None)

        for i, control in enumerate(self.control_names):
            if i >= self.control_size:
                continue
            real_control = tf.slice(real_action, [0, i], [-1, 1])
            action_index = self.action_name_index_map[control]

            if action_index == COMBO:
                real_index = self.combo_name_index_map[control]
                action_size = self.combo_action_sizes[real_index]
                bucketed_control = real_control
                if action_size > 2:
                    bucketed_control = self.round_action_graph(real_control, action_size)
                combo_list[real_index] = bucketed_control
            else:
                if indexes[action_index] is None:
                    indexes[action_index] = self._find_closet_real_number_graph(real_control)
        combo_action = self._create_combo_index_graph(combo_list, real_action)
        if batch_size is not None and batch_size == 1:
            indexes[self.action_name_index_map[COMBO]] = tf.reshape(combo_action, [1])
        else:
            indexes[self.action_name_index_map[COMBO]] = tf.squeeze(combo_action)

        result = tf.stack(indexes, axis=1)
        return result
