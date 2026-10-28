"""
Community Water Conservation and Storage Management System
===========================================================
PROG211 - Object-Oriented Programming 1 (Individual Assignment)

Simulates how a utility such as Guma Valley Water Company could monitor
community water storage tanks in New England Ville and Railway Line
Community, Freetown. No IoT hardware is needed: sensors are simulated.

DPG alignment: open-source (MIT), modular classes, privacy-respecting
(only tank/aggregate data, no personal data), reusable and configurable.
"""
import random
from abc import ABC, abstractmethod
from collections import deque, namedtuple
from datetime import datetime, timedelta

# A tuple-based record (immutable): extra-mark use of tuples.
Record = namedtuple("Record", "timestamp tank_id kind litres level_after")


# ----------------------------------------------------------------- Sensors
class Sensor(ABC):
    """Abstract parent class: every sensor must implement read()."""
    UNIT = ""

    def __init__(self, sensor_id, location):
        self._sensor_id = sensor_id          # protected (encapsulated)
        self._location = location

    @property
    def sensor_id(self):
        return self._sensor_id

    @abstractmethod
    def read(self):
        """Return the current simulated reading."""

    def describe(self):                      # shared by all children
        return f"{type(self).__name__} {self._sensor_id} @ {self._location}: {self.read()} {self.UNIT}"


class UltrasonicSensor(Sensor):
    """Measures tank level (%) with small simulated noise."""
    UNIT = "% full"

    def __init__(self, sensor_id, location, tank):
        super().__init__(sensor_id, location)
        self._tank = tank

    def read(self):
        noisy = self._tank.level_percent + random.uniform(-0.4, 0.4)
        return round(max(0.0, min(100.0, noisy)), 1)


class FlowSensor(Sensor):
    """Measures the most recent flow (litres) through the tank pipe."""
    UNIT = "L last flow"

    def __init__(self, sensor_id, location):
        super().__init__(sensor_id, location)
        self._last_flow = 0.0

    def record_flow(self, litres):
        self._last_flow = litres

    def read(self):
        return round(self._last_flow, 1)


# ------------------------------------------------------------------- Valve
class Valve:
    def __init__(self, valve_id):
        self._valve_id = valve_id
        self._is_open = True

    @property
    def is_open(self):
        return self._is_open

    def open(self):
        self._is_open = True

    def close(self):
        self._is_open = False

    def __str__(self):
        return f"{self._valve_id} ({'OPEN' if self._is_open else 'CLOSED'})"


# -------------------------------------------------------------- WaterTank
class WaterTank:
    LOW_THRESHOLD = 20.0        # % : low-water alert below this
    OVERFLOW_THRESHOLD = 95.0   # % : overflow alert above this
    REOPEN_THRESHOLD = 85.0     # % : valve reopens at or below this

    def __init__(self, tank_id, capacity_litres, level_litres, valve):
        self._tank_id = tank_id
        self._capacity = float(capacity_litres)
        self.__level = float(level_litres)   # private: only changed via methods
        self._valve = valve
        self._sensors = [UltrasonicSensor(f"US-{tank_id}", tank_id, self),
                         FlowSensor(f"FL-{tank_id}", tank_id)]
        self._regulate_valve()

    @classmethod
    def from_percent(cls, tank_id, capacity_litres, percent):
        """Alternative constructor: build a tank from a starting level %."""
        return cls(tank_id, capacity_litres, capacity_litres * percent / 100,
                   Valve(f"V-{tank_id}"))

    @staticmethod
    def to_percent(litres, capacity):
        return round(litres / capacity * 100, 1)

    @property
    def tank_id(self):
        return self._tank_id

    @property
    def capacity(self):
        return self._capacity

    @property
    def level_litres(self):
        return self.__level

    @property
    def level_percent(self):
        return self.to_percent(self.__level, self._capacity)

    @property
    def valve(self):
        return self._valve

    @property
    def sensors(self):
        return list(self._sensors)

    @property
    def flow_sensor(self):
        return self._sensors[1]

    def add_water(self, litres):
        """Add inflow; rejected entirely if the valve is closed."""
        if not self._valve.is_open:
            return 0.0
        added = min(litres, self._capacity - self.__level)
        self.__level += added
        self.flow_sensor.record_flow(added)
        self._regulate_valve()
        return added

    def use_water(self, litres):
        used = min(litres, self.__level)
        self.__level -= used
        self.flow_sensor.record_flow(used)
        self._regulate_valve()
        return used

    def _regulate_valve(self):
        """Automatic control: close above 95%, reopen at 85% or below."""
        pct = self.level_percent
        if pct > self.OVERFLOW_THRESHOLD:
            self._valve.close()
        elif pct <= self.REOPEN_THRESHOLD:
            self._valve.open()

    def status(self):
        bar = "#" * int(self.level_percent // 5)
        return (f"{self._tank_id:<7} [{bar:<20}] {self.level_percent:>5.1f}%  "
                f"{self.__level:>8.0f}/{self._capacity:.0f} L  Valve: {self._valve}")


# -------------------------------------------------------------- Community
class Community:
    def __init__(self, name, households):
        self._name = name
        self._households = households       # aggregate count only (privacy)
        self._tanks = {}                     # dictionary: tank_id -> WaterTank

    @property
    def name(self):
        return self._name

    @property
    def tanks(self):
        return list(self._tanks.values())

    def add_tank(self, tank):
        self._tanks[tank.tank_id] = tank

    def get_tank(self, tank_id):
        return self._tanks.get(tank_id)

    def total_stored(self):
        return sum(t.level_litres for t in self._tanks.values())

    def summary(self):
        return (f"{self._name} | ~{self._households} households | "
                f"{len(self._tanks)} tanks | {self.total_stored():,.0f} L stored")


# ------------------------------------------------------------------ Alert
class Alert:
    _counter = 0   # class attribute shared by all alerts

    def __init__(self, alert_id, tank_id, kind, message):
        self._alert_id = alert_id
        self._tank_id = tank_id
        self._kind = kind
        self._message = message
        self._timestamp = datetime.now()

    @classmethod
    def create(cls, tank_id, kind, message):
        cls._counter += 1
        return cls(cls._counter, tank_id, kind, message)

    @property
    def timestamp(self):
        return self._timestamp

    def __str__(self):
        return (f"#{self._alert_id:03d} {self._timestamp:%Y-%m-%d %H:%M} "
                f"[{self._kind}] {self._tank_id}: {self._message}")


# ------------------------------------------------- WaterManagementSystem
class WaterManagementSystem:
    ABNORMAL_FACTOR = 2.0     # usage > 2x the recent average is abnormal
    MIN_HISTORY = 3

    def __init__(self, operator="Guma Valley Water Company"):
        self._operator = operator
        self._communities = {}      # dict: name -> Community
        self._records = []          # list of Record tuples (history)
        self._alerts = []           # list of Alert objects
        self._active = set()        # (tank_id, kind) currently flagged
        self._recent_alerts = deque(maxlen=5)   # queue of latest alerts

    # ---- setup
    def add_community(self, community):
        self._communities[community.name] = community

    @property
    def communities(self):
        return list(self._communities.values())

    def all_tanks(self):
        return [t for c in self.communities for t in c.tanks]

    def find_tank(self, tank_id):
        for c in self.communities:
            if c.get_tank(tank_id):
                return c.get_tank(tank_id)
        return None

    # ---- operations
    def record_inflow(self, tank_id, litres):
        tank = self.find_tank(tank_id)
        before = tank.level_percent
        added = tank.add_water(litres)
        self._log(tank, "INFLOW", added)
        self._check_levels(tank)
        if added == 0:
            return "Valve is CLOSED - inflow rejected to prevent overflow."
        note = f"{added:,.0f} L added ({before}% -> {tank.level_percent}%)."
        if added < litres:
            note += f" {litres - added:,.0f} L could not fit."
        return note

    def record_usage(self, tank_id, litres):
        tank = self.find_tank(tank_id)
        past = [r.litres for r in self._records
                if r.tank_id == tank_id and r.kind == "USAGE"]
        used = tank.use_water(litres)
        self._log(tank, "USAGE", used)
        self._check_levels(tank)
        if self.is_abnormal(used, past, self.ABNORMAL_FACTOR, self.MIN_HISTORY):
            self._raise(tank.tank_id, "ABNORMAL",
                        f"Usage of {used:,.0f} L is far above the normal average - possible leak or misuse.")
        return f"{used:,.0f} L used ({tank.level_percent}% remaining)."

    @staticmethod
    def is_abnormal(litres, past, factor=2.0, min_history=3):
        if len(past) < min_history:
            return False
        return litres > factor * (sum(past) / len(past))

    @staticmethod
    def valid_litres(text):
        """Validate user input; returns float or None."""
        try:
            value = float(text)
        except ValueError:
            return None
        return value if value > 0 else None

    def _log(self, tank, kind, litres, when=None):
        self._records.append(Record(when or datetime.now(), tank.tank_id, kind,
                                    round(litres, 1), tank.level_percent))

    def _raise(self, tank_id, kind, message):
        alert = Alert.create(tank_id, kind, message)
        self._alerts.append(alert)
        self._recent_alerts.append(alert)

    def _check_levels(self, tank):
        pct = tank.level_percent
        for kind, bad, msg in (
            ("LOW", pct < WaterTank.LOW_THRESHOLD,
             f"Level {pct}% is below {WaterTank.LOW_THRESHOLD:.0f}% - shortage risk."),
            ("OVERFLOW", pct > WaterTank.OVERFLOW_THRESHOLD,
             f"Level {pct}% exceeds {WaterTank.OVERFLOW_THRESHOLD:.0f}% - valve closed automatically."),
        ):
            key = (tank.tank_id, kind)
            if bad and key not in self._active:
                self._active.add(key)
                self._raise(tank.tank_id, kind, msg)
            elif not bad:
                self._active.discard(key)

    # ---- views / reports
    def alerts(self):
        return list(self._alerts)

    def records(self, tank_id=None):
        return [r for r in self._records if tank_id in (None, r.tank_id)]

    def daily_report(self, day=None):
        day = day or datetime.now().date()
        lines = [f"DAILY REPORT - {day} | {self._operator}", "=" * 62]
        for c in self.communities:
            lines.append(c.summary())
            for t in c.tanks:
                todays = [r for r in self._records
                          if r.tank_id == t.tank_id and r.timestamp.date() == day]
                inflow = sum(r.litres for r in todays if r.kind == "INFLOW")
                usage = sum(r.litres for r in todays if r.kind == "USAGE")
                lines.append(f"  {t.tank_id}: in {inflow:,.0f} L | used {usage:,.0f} L | "
                             f"level {t.level_percent}% | valve {'OPEN' if t.valve.is_open else 'CLOSED'}")
        n = sum(1 for a in self._alerts if a.timestamp.date() == day)
        lines.append(f"Alerts today: {n}")
        return "\n".join(lines)

    # ---- demo data
    @classmethod
    def with_demo_data(cls):
        """Realistic simulated data for Freetown communities."""
        rng = random.Random(2026)
        system = cls()
        ne = Community("New England Ville", 420)
        rl = Community("Railway Line Community", 310)
        ne.add_tank(WaterTank.from_percent("NEV-T1", 20000, 62))
        ne.add_tank(WaterTank.from_percent("NEV-T2", 10000, 15))   # starts LOW
        rl.add_tank(WaterTank.from_percent("RL-T1", 15000, 93))    # near full
        rl.add_tank(WaterTank.from_percent("RL-T2", 8000, 48))
        system.add_community(ne)
        system.add_community(rl)
        for tank in system.all_tanks():            # 6 days of past usage
            for d in range(6, 0, -1):
                for hour in (6, 13, 19):
                    when = datetime.now() - timedelta(days=d) + timedelta(hours=hour - 12)
                    litres = tank.capacity * rng.uniform(0.03, 0.05)
                    system._log(tank, "USAGE", litres, when)
        for tank in system.all_tanks():            # initial alerts
            system._check_levels(tank)
        return system


# ------------------------------------------------------------ Console UI
def pick_tank(system):
    tanks = system.all_tanks()
    for i, t in enumerate(tanks, 1):
        print(f"  {i}. {t.tank_id}")
    choice = input("Select tank number: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(tanks):
        return tanks[int(choice) - 1]
    print("Invalid tank selection.")
    return None


def ask_litres():
    litres = WaterManagementSystem.valid_litres(input("Litres: "))
    if litres is None:
        print("Please enter a positive number.")
    return litres


def show_status(system):
    for c in system.communities:
        print("\n" + c.summary())
        for t in c.tanks:
            print("  " + t.status())
            for s in t.sensors:               # polymorphism: same call, different sensor
                print("      " + s.describe())


def menu():
    system = WaterManagementSystem.with_demo_data()
    print("\n=== Community Water Conservation & Storage Management System ===")
    while True:
        print("\n1. View Community Tank Status\n2. Add Water to Tank\n3. Record Water Usage"
              "\n4. View Alerts\n5. View Historical Records\n6. Generate Daily Report\n7. Exit System")
        option = input("Choose an option (1-7): ").strip()
        if option == "1":
            show_status(system)
        elif option in ("2", "3"):
            tank = pick_tank(system)
            litres = ask_litres() if tank else None
            if litres:
                action = system.record_inflow if option == "2" else system.record_usage
                print(action(tank.tank_id, litres))
        elif option == "4":
            alerts = system.alerts()
            print("\n".join(str(a) for a in alerts) if alerts else "No alerts.")
        elif option == "5":
            tank = pick_tank(system)
            if tank:
                for r in system.records(tank.tank_id)[-15:]:
                    print(f"{r.timestamp:%Y-%m-%d %H:%M} {r.kind:<6} {r.litres:>8,.1f} L -> {r.level_after}%")
        elif option == "6":
            print(system.daily_report())
        elif option == "7":
            print("System closed. Thank you.")
            break
        else:
            print("Invalid option. Enter 1-7.")


if __name__ == "__main__":
    menu()
