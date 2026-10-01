"""Edition et reordonnancement des actions clavier."""


def populate_list(self):
    self.is_updating_ui = True
    self.list_widget.clear()
    for i, action in enumerate(self.temp_actions):
        display_name = action['name']
        if i < 9:
            display_name = f"{i+1}  •  {display_name}"
        self.list_widget.addItem(display_name)
    self.is_updating_ui = False
    if self.temp_actions:
        self.list_widget.setCurrentRow(0)


def on_action_selected(self, row):
    if self.is_updating_ui or row < 0: return
    self.is_updating_ui = True
    action = self.temp_actions[row]
    self.name_input.setText(action['name'])
    self.sys_prompt_input.setText(action['system_prompt'])
    self.prefix_input.setText(action['prompt_prefix'])
    self.is_updating_ui = False


def update_action_field(self):
    if self.is_updating_ui: return
    row = self.list_widget.currentRow()
    if row >= 0:
        self.temp_actions[row]['name'] = self.name_input.text()
        self.temp_actions[row]['system_prompt'] = self.sys_prompt_input.toPlainText()
        self.temp_actions[row]['prompt_prefix'] = self.prefix_input.text()

        display_name = self.name_input.text()
        if row < 9:
            display_name = f"{row+1}  •  {display_name}"
        self.list_widget.item(row).setText(display_name)


def add_action(self):
    self.temp_actions.append({"name": "Nouvelle Action", "system_prompt": "Tu es un assistant IA.", "prompt_prefix": ""})
    self.populate_list()
    self.list_widget.setCurrentRow(len(self.temp_actions) - 1)


def del_action(self):
    row = self.list_widget.currentRow()
    if row >= 0:
        del self.temp_actions[row]
        self.populate_list()


def move_action(self, direction):
    row = self.list_widget.currentRow()
    if 0 <= row + direction < len(self.temp_actions):
        self.temp_actions[row], self.temp_actions[row + direction] = self.temp_actions[row + direction], self.temp_actions[row]
        self.populate_list()
        self.list_widget.setCurrentRow(row + direction)
