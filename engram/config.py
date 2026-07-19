"""All tunable constants. Sim-time unit is days (float)."""

HALF_LIFE_EPISODE = 3.0                # sim-days
HALF_LIFE_EPISODE_CONSOLIDATED = 1.0   # gist survives, detail fades
HALF_LIFE_FACT = 14.0
RETRIEVAL_BOOST = 0.3
STRENGTH_CAP = 1.0
DORMANT_THRESHOLD = 0.15               # below this: excluded from recall, never deleted
REFUSAL_THRESHOLD = 0.25               # best retrieval score below this -> refuse
TOP_K = 6
SIM_EDGE_THRESHOLD = 0.75              # fact<->fact similarity edges in graph()
MAX_EPISODES = 200                     # demo cap; oldest-dormant dropped beyond it
