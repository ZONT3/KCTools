import re

import requests
from IPython.display import display, Markdown
from bs4 import BeautifulSoup

from util import *


class Quest:
    def __init__(self, id, data):
        self.id = id
        self.code = data['code']
        self.required = set()
        self.unlocks = set()

        if 'name' in data:
            self.name = data['name']
        else:
            self.name = 'unknown'
        if 'desc' in data:
            self.desc = data['desc']
        else:
            self.desc = None
        if 'memo' in data:
            self.memo = data['memo']
        else:
            self.memo = None

    def add_requirement(self, other):
        self.required.add(other)

    def get_requirements(self):
        return self.required

    def add_unlock(self, other):
        self.unlocks.add(other)

    def __str__(self):
        return f'[{self.code}]'

    def __repr__(self):
        return f'Quest({self.code})'

    def str_link(self):
        res = f'[{self.code}](https://en.kancollewiki.net/Quests#{self.code})'
        return res


class QuestData:
    def __init__(self, quests_data, quests_my, scrap_wiki=True, verbose=False):
        self.quests_data = quests_data
        self.quests = self._init_from(quests_data)
        self.quests_my_raw = quests_my
        self.quests_my = None

        if scrap_wiki:
            self.populate_from_wiki(verbose)

    def find_quest(self, code):
        """
        Find quest by its code
        :param code: Quest code, like 'Bm5' or 'A90'
        :return: Quest object or None if not found
        """
        for q in self.quests.values():
            if q.code == code:
                return q

    def is_available(self, quest: Quest):
        """
        Predicate to test if quest presents in player's data and its state is either 1, 2 or 3
        :param quest: Quest object to test
        :return: Is Quest available
        """
        return quest.id in self.quests_my_raw and self.quests_my_raw[quest.id]['status'] in (1, 2, 3)

    def is_completed(self, quest: Quest):
        """
        Predicate to test if quest presents in player's data and its state is 3
        :param quest: Quest object to test
        :return: Is Quest completed
        """
        return quest.id in self.quests_my_raw and self.quests_my_raw[quest.id]['status'] == 3

    def is_last(self, quest: Quest):
        """
        Predicate to test if quest is active,
        or all its requirements leads to quests with empty requirements and without active ones
        :param quest: Quest object to test
        :return: Is this quest last in chain
        """
        if self.is_available(quest):
            return True
        if len(quest.get_requirements()) == 0:
            return True
        for q in quest.get_requirements():
            if self.is_available(q) or not self.is_last(q):
                return False
        return True

    def quest_tree(self, quest_code):
        """
        Display quest info, its tree, and all encountered quests info.
        Quests, which can be selected in game (according to kc3data file), should be outer vertices of tree.
        :param quest_code: Code of target quest, like 'Bm5' or 'A90'.
        """
        target = self.find_quest(quest_code)
        tree, total = requirements_tree(target,
                                        self.is_last,
                                        lambda q: str(q) + (
                                            '(V)' if self.is_completed(q) else
                                            ('(X)' if self.is_available(q) else '')
                                        ))

        target_md = quest_to_md(target, h_lvl=3)
        tree = '\n'.join(['```', tree, '```'])

        other_quests = [q for q in total if q != target and not self.is_completed(q)]
        other_quests.sort(key=lambda x: 0 if self.is_available(x) else 1)
        other_quests_md = [quest_to_md(q, h_lvl=4, mark=self.is_available(q)) for q in other_quests]
        other_quests_md = '\n'.join(other_quests_md)

        display(Markdown('\n'.join([target_md, tree, other_quests_md, '***'])))

    def populate_from_wiki(self, verbose=False):
        info("Parsing requirements from wiki")
        present = 0
        found = 0
        error = 0
        unknown = 0

        soup = BeautifulSoup(requests.get('https://en.kancollewiki.net/Quests').content, features='lxml')
        for tr in soup.find_all('tr', recursive=True):
            if not tr.has_attr('id') or not tr.has_attr('style'):
                continue
            if not tr['style'].startswith('border-top: 3px'):
                continue

            code = tr['id']
            quest = self.find_quest(code)
            if quest is None:
                warn(f"Unknown quest {code}")
                continue

            error += 1

            notes = tr.find_next_sibling('tr').find_next_sibling('tr')
            if notes is None:
                if verbose:
                    err(f"Failed to get reqs on stage 1 (notes node) for quest {code}")
                continue

            notes_content = notes.find('td', {'style': 'text-align: left;'})
            if notes_content is None:
                if verbose:
                    err(f"Failed to get reqs on stage 2 (notes content) for quest {code}")
                continue

            notes_content = str(notes_content)
            reqs_str = re.match(r'.*Requires: (<a.+?>.+?</a>)(?=<br|$)', notes_content, flags=re.M)
            if reqs_str is None:
                if verbose:
                    err(f"Failed to get reqs on stage 3 (notes regex) for quest {code}")
                continue

            error -= 1

            reqs_str = reqs_str.group(1)
            for r_code in re.findall(r"<a.+?>(.+?)</a>", reqs_str):
                q = self.find_quest(r_code)
                if not q:
                    if verbose:
                        warn(f"Unknown requirement for quest {code}: {r_code}")
                    unknown += 1
                    continue
                if q not in quest.get_requirements():
                    quest.add_requirement(q)
                    q.add_unlock(quest)
                    found += 1
                    if verbose:
                        info(f"Found missing requirement for {code}: {r_code}")
                else:
                    present += 1

        info(f"Failed to get requirements: {error}")
        info(f"Unknown requirements: {unknown}")
        info(f"Found missing in KC3 reqs: {found}")
        info(f"Found req but already present in KC3: {present}")
        info(f"KC3 data reliability (present req vs total reqs): {int((present / (found + present)) * 100):02d}%")

    def get_my_quests(self):
        if self.quests_my:
            return self.quests_my

        self.quests_my = {k: v for k, v in self.quests.items() if self.is_available(v)}
        return self.quests_my

    @staticmethod
    def _init_from(store_from):
        store_to = dict()
        for idx, data in store_from.items():
            store_to[idx] = Quest(idx, data)
        for idx, data in store_from.items():
            if 'unlock' not in data:
                continue

            this_quest = store_to[idx]
            for unlock_id in data['unlock']:
                unlock_id = str(unlock_id)
                if unlock_id not in store_to:
                    warn(f"Quest [{idx}] {data['code']} unlocks unknown quest {unlock_id}")
                    continue

                quest = store_to[unlock_id]
                this_quest.add_unlock(quest)
                quest.add_requirement(this_quest)

        return store_to


def quest_to_md(quest, h_lvl=3, mark=False):
    """
    Format quest as Markdown string. Quest name will be presented as header (#)
    :param quest: Quest to format
    :param h_lvl: header level (1-4)
    :param mark: True it needs to be marked
    :return: Markdown formatted string
    """
    md = [f"{'#' * max(1, min(4, h_lvl))} [{quest.str_link()}] "]
    if mark:
        md.append(f'[X] __{quest.name}__')
    else:
        md.append(quest.name)
    if quest.desc is not None:
        md.append('\n')
        md.append(f'**{quest.desc}**')
        md.append('\n')
    if quest.memo is not None:
        md.append('\n')
        md.append(quest.memo)
        md.append('\n')
    md.append('\n')

    return ''.join(md)


def requirements_tree(quest: Quest, fnc_terminate=lambda x: False, fnc_str=lambda q: str(q), ident=0, lines=None,
                      total=None):
    """
    Recursion for tree string generation
    :param quest: Target (root) quest
    :param fnc_terminate: Predicate to terminate at (usually, a check for quest to be available in KC to select)
    :param fnc_str: Quest-String function to properly display the quest
    :param ident: Indentation to start at (internal, used in recursion)
    :param lines: Positions, where lines (branches of tree) should be inserted for now (internal, used in recursion)
    :param total: Current set of total encountered quests (internal, used in recursion)
    :return: str: generated tree multiline string, set: total encountered quests (including root one)
    """
    if total is None: total = set()
    if lines is None: lines = []

    res = []
    total.add(quest)

    terminate = fnc_terminate(quest)
    reqs = quest.get_requirements()
    reqs_len = len(reqs)

    if terminate or reqs_len <= 0:
        res.append(fnc_str(quest))

    else:
        res.append(fnc_str(quest))
        for i, req in enumerate(reqs):
            last = (i + 1) >= reqs_len
            res.append('\n')

            ident_str = ' ' * ident
            for idx in lines:
                ident_str = ''.join((ident_str[:idx], '│', ident_str[idx + 1:] if idx + 1 < len(ident_str) else ''))
            res.append(ident_str)

            res.append('└' if last else '├')
            res.append('─')

            reqs_str, _ = requirements_tree(req,
                                            fnc_terminate=fnc_terminate,
                                            fnc_str=fnc_str,
                                            ident=ident + 2,
                                            lines=lines if last else lines + [ident],
                                            total=total)
            res.append(reqs_str)

    return ''.join(res), total
