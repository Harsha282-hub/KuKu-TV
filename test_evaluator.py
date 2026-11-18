"""Offline unit tests; does not contact Ollama."""
import tempfile
import unittest
from pathlib import Path
from ollama_evaluate import parse_judgment, signature, atomic_json, export

GOOD = {'hook_score':8,'cliffhanger_score':9,'clarity_score':7,'emotion_score':8,
        'rationale':'Strong opening and unresolved threat.', 'hook_evidence':'A threat.',
        'cliffhanger_evidence':'The threat remains unresolved.', 'needs_video_review':True}
CLIP = {'clip_id':1,'episode':1,'start':0,'end':20,'duration':20,
        'events':[{'start':0,'end':3,'type':'dialogue','speaker':'A','text':'Stop!'}]}

class EvaluatorTests(unittest.TestCase):
    def test_scores(self):
        x=parse_judgment(GOOD)
        self.assertAlmostEqual(x['overall_score'],8.05)
    def test_reject_invalid(self):
        with self.assertRaises(ValueError): parse_judgment({**GOOD,'hook_score':12})
    def test_cache_invalidation(self):
        self.assertNotEqual(signature(CLIP,'qwen2.5:7b',0),signature({**CLIP,'end':21},'qwen2.5:7b',0))
    def test_export_cached(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t); cache=root/'cache'; cache.mkdir()
            key=signature(CLIP,'qwen2.5:7b',0)
            atomic_json(cache/f'clip_001_{key[:16]}.json',{'signature':key,'evaluation':GOOD})
            n=export([CLIP],cache,root/'results','qwen2.5:7b',0)
            self.assertEqual(n,1)
            self.assertTrue((root/'results'/'ollama_ranked_promos.csv').exists())

if __name__=='__main__':unittest.main()
