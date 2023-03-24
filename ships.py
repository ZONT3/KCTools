from tqdm import tqdm

KNOWN_ALTERS = {
    'Comdt. Teste': ('Commandant Teste',),
    'Comdt. Teste Kai': ('Commandant Teste Kai',)
}


class Ship:
    def __init__(self, id, data, models):
        self.id = id
        self.name = data['Name']
        self.type = data['SType'].split('/')[-1]
        self.models = [m[1] for m in models]
        self.models_str = [
            f'#{i + 1}: {m[1]}' if len(models) > 1 else m[1]
            for i, m in enumerate(models)
        ]
        self.models_idx = [m[0] for m in models]

    def __str__(self):
        return self.name

    def __repr__(self):
        return f'Ship({self.name})'


class ShipData:
    def __init__(self, ships_data, ships_my):
        self.ships_data = ships_data
        self.ships_my_raw = ships_my
        self.ships = self.from_data(ships_data)
        self.ships_my = {
            self.find_ship(s['masterId'])
            for s in ships_my.values()
        }
        self.ships_my = {k.id: self.ships[k.id] for k in self.ships_my if k is not None}

    def find_ship(self, idx):
        if idx in self.ships:
            return self.ships[idx]

        for _, s in self.ships.items():
            if idx in s.models_idx:
                return s

    @staticmethod
    def from_data(data):
        res = dict()
        for idx, s in data.iterrows():
            first_model = int(s['Models'].split('/')[0])
            if first_model != idx:
                continue
            res[idx] = Ship(idx, s, ShipData.find_models(idx, data))
        return res

    def find_quests(self, qd):
        found = dict()

        for q in tqdm(qd.get_my_quests().values()):
            found_ships = []
            for s in self.ships.values():
                for i, m in reversed(list(enumerate([s.name] + s.models))):
                    if any(
                            q.desc.count(x) > 0
                            for x in (
                                    (m,) + KNOWN_ALTERS[m]
                                    if m in KNOWN_ALTERS else
                                    (m,)
                            )):
                        found_ships.append((
                            ([s.name] + s.models_str)[i],
                            s.id in self.ships_my
                        ))
                        break

            if len(found_ships) > 0:
                found[q] = found_ships

        return found

    @staticmethod
    def find_models(idx, data):
        models = list(map(lambda x: int(x), data['Models'][idx].split('/')))
        return [(i, m['Name']) for i, m in data.loc[models[1:]].iterrows()]
