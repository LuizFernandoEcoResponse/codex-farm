import json, tempfile, time, unittest
from pathlib import Path
from fastapi.testclient import TestClient
from codexfarm import store
from codexfarm.api import app
import codexfarm.graph as graph

class FakeProvider:
    def run(self,prompt,cwd,autonomy,mission_id=None):
        if "Audit the following" in prompt: return "PASS: claims have sources; gaps noted."
        return "Evidence with source https://example.org/source and limitations."

class MissionFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); store.DB_PATH=Path(self.tmp.name)/"farm.sqlite3"; store.init_db()
        self.original=graph.provider; graph.provider=FakeProvider()
        self.client=TestClient(app)
    def tearDown(self):
        graph.provider=self.original; self.client.close(); self.tmp.cleanup()
    def test_mission_runs_three_parallel_workers_and_persists_audit(self):
        response=self.client.post("/api/missions",json={"title":"Test mission","goal":"Research testable claims and evidence across the domain.","autonomy":"balanced","budget_usd":10})
        self.assertEqual(response.status_code,201,response.text)
        mid=response.json()["id"]
        deadline=time.time()+8
        while time.time()<deadline:
            item=self.client.get(f"/api/missions/{mid}").json()
            if item["status"] in ("completed","failed"): break
            time.sleep(.05)
        self.assertEqual(item["status"],"completed",item)
        self.assertEqual(len(item["tasks"]),3)
        self.assertTrue(all(t["status"]=="completed" and t["result"] for t in item["tasks"]))
        self.assertTrue(any(e["kind"]=="audit.completed" for e in item["events"]))
    def test_supervised_mode_waits_until_approved(self):
        response=self.client.post("/api/missions",json={"title":"Approval test","goal":"Research a sufficiently detailed test goal with citations.","autonomy":"supervised"})
        self.assertEqual(response.status_code,201)
        item=self.client.get(f"/api/missions/{response.json()['id']}").json()
        self.assertEqual(item["status"],"awaiting_approval")
        self.assertTrue(all(t["status"]=="queued" for t in item["tasks"]))
    def test_budget_input_cannot_exceed_configured_ceiling(self):
        response=self.client.post("/api/missions",json={"title":"Budget test","goal":"Research a sufficiently detailed test goal with citations.","budget_usd":10.01})
        self.assertEqual(response.status_code,422)

    def test_interrupted_running_work_is_queued_on_restart(self):
        mid=store.create_mission("Recovery test","Recover interrupted agent work without duplicating results.","balanced",10,[{"role":"Research analyst","prompt":"Find evidence"}])
        item=store.get_mission(mid); tid=item["tasks"][0]["id"]
        self.assertTrue(store.claim_task(tid))
        store.transition(mid,"running")
        store.init_db()
        recovered=store.get_mission(mid)
        self.assertEqual(recovered["status"],"queued")
        self.assertEqual(recovered["tasks"][0]["status"],"queued")
        self.assertEqual(recovered["tasks"][0]["attempts"],1)
