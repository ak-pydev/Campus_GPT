"""
gaze_graph_rl_chunking.py

Gaze-Informed Graph-RL Chunking:
 - Streams eye-tracking data (PyEyeTrack) for gaze co-attention.
 - Builds a semantic-gaze graph (NetworkX + python-louvain).
 - Applies RL (Stable-Baselines3 PPO) to optimize chunk boundaries for retrieval.
"""

import asyncio
import json
import cv2
import numpy as np
import networkx as nx
import community as community_louvain  # python-louvain
from rank_bm25 import BM25Okapi
from stable_baselines3 import PPO
from stable_baselines3.common.envs import DummyVecEnv
from sentence_transformers import SentenceTransformer
from pyeyetrack import EyeTracker  # from PyEyeTrack
from typing import List, Tuple

# ─── CONFIG ─────────────────────────────────────────────────────────────────
DOCUMENT_PATH = "input/document.txt"
QA_PAIRS_PATH = "input/qa_pairs.jsonl"
RL_MODEL_PATH = "models/chunk_ppo.zip"
OUTPUT_CHUNKS = "output/chunks.json"
DEVICE = "cuda" if __import__("torch").cuda.is_available() else "cpu"

# ─── LOAD MODELS ─────────────────────────────────────────────────────────────
embedder = SentenceTransformer("multi-qa-MiniLM-L6-cos-v1", device=DEVICE)

# ─── UTILS ───────────────────────────────────────────────────────────────────
def load_sentences(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    # simple split by period; replace with spaCy for better segmentation
    return [s.strip() for s in text.split(".") if s.strip()]

def sentence_embeddings(sents: List[str]) -> np.ndarray:
    return embedder.encode(sents, normalize_embeddings=True)

def build_semantic_gaze_graph(
    sents: List[str],
    embs: np.ndarray,
    gazes: np.ndarray
) -> nx.Graph:
    """
    gazes: N x T matrix of fixation counts per sentence over time window T.
    """
    G = nx.Graph()
    N = len(sents)
    # add nodes
    for i in range(N):
        G.add_node(i)
    # compute weights
    for i in range(N):
        for j in range(i + 1, N):
            # cosine similarity
            cos_sim = float(np.dot(embs[i], embs[j]))
            # co-attention: normalized dot of gaze vectors
            gaze_co = float(np.dot(gazes[i], gazes[j]) /
                           (np.linalg.norm(gazes[i]) * np.linalg.norm(gazes[j]) + 1e-8))
            w = 0.7 * cos_sim + 0.3 * gaze_co
            if w > 0.1:  # threshold to sparsify
                G.add_edge(i, j, weight=w)
    return G

def detect_initial_chunks(G: nx.Graph) -> List[int]:
    # returns dict: node -> community id
    partition = community_louvain.best_partition(G, weight="weight")
    # convert to list of chunk ids per sentence
    return [partition[i] for i in range(len(partition))]

# ─── EYE-TRACKING STREAM ─────────────────────────────────────────────────────
async def collect_gaze(sents: List[str]) -> np.ndarray:
    """
    Use PyEyeTrack to map each fixation to sentence indices.
    Returns: N_sentences x T time-bins gaze matrix.
    """
    tracker = EyeTracker()  # init default webcam
    gaze_counts = np.zeros((len(sents), 1000), dtype=float)
    # collect for 10 seconds at 100Hz
    for t in range(1000):
        frame = tracker.get_frame()
        gx, gy = tracker.get_gaze_point()  # normalized coords
        # naive mapping: linearly assign to sentence by y-position
        idx = int(gy * len(sents))
        if 0 <= idx < len(sents):
            gaze_counts[idx, t] += 1
        await asyncio.sleep(0.01)
    tracker.stop()
    return gaze_counts

# ─── RL ENVIRONMENT ──────────────────────────────────────────────────────────
import gym
from gym import spaces

class ChunkEnv(gym.Env):
    """
    State: current chunk assignments (list of ints)
    Action: (i, delta) -> move boundary at sentence i by delta ∈ {-1,0,+1}
    Reward: retrieval F1 on held-out QA.
    """
    def __init__(self, sents, qa_pairs, bm25, embeddings):
        super().__init__()
        self.sents = sents
        self.qa_pairs = qa_pairs
        self.bm25 = bm25
        self.embeddings = embeddings
        self.n = len(sents)
        # state: chunk id per sentence
        self.state = np.zeros(self.n, dtype=int)
        # action space: pairs (i, delta)
        self.action_space = spaces.MultiDiscrete([self.n, 3])
        # observation: chunk ids flattened
        self.observation_space = spaces.Box(0, self.n, shape=(self.n,), dtype=int)

    def reset(self):
        self.state = detect_initial_chunks(self._G)
        return self.state.copy()

    def step(self, action):
        i, delta = action
        # adjust boundary: reassign sentence i's chunk
        self.state[i] = max(0, min(self.n - 1, self.state[i] + (delta - 1)))
        # compute reward
        reward = self._evaluate_retrieval()
        done = True  # single-step episode
        return self.state.copy(), reward, done, {}

    def render(self, mode="human"):
        pass

    def _evaluate_retrieval(self) -> float:
        # flatten chunks into passages
        passages = []
        for cid in sorted(set(self.state.tolist())):
            text = " ".join([self.sents[i] for i in range(self.n) if self.state[i] == cid])
            passages.append(text)
        # BM25 on sentences
        bm25 = BM25Okapi([p.split() for p in passages])
        # evaluate on QA pairs
        correct = 0
        for qa in self.qa_pairs:
            scores = bm25.get_scores(qa["question"].split())
            best = np.argmax(scores)
            if passages[best].startswith(qa["answer"][:20]):
                correct += 1
        return correct / len(self.qa_pairs)

# ─── MAIN ────────────────────────────────────────────────────────────────────
async def main():
    sents = load_sentences(DOCUMENT_PATH)
    embs = sentence_embeddings(sents)
    qa_pairs = [json.loads(l) for l in open(QA_PAIRS_PATH)]
    # gaze collection
    gazes = await collect_gaze(sents)
    # build graph
    G = build_semantic_gaze_graph(sents, embs, gazes)
    # prepare BM25 passages placeholder
    bm25 = BM25Okapi([s.split() for s in sents])
    # RL environment
    env = DummyVecEnv([lambda: ChunkEnv(sents, qa_pairs, bm25, embs)])
    model = PPO("MlpPolicy", env, verbose=1)
    model.learn(total_timesteps=10000)
    model.save(RL_MODEL_PATH)
    # final chunking
    env_inst = env.envs[0]
    chunks = env_inst.state.tolist()
    with open(OUTPUT_CHUNKS, "w") as f:
        json.dump({"sentences": sents, "chunks": chunks}, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
