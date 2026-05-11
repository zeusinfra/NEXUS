import unittest

from zeus_core.event_pipeline import OverflowEventQueue


class EventPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_overflow_queue_drops_oldest_event(self):
        queue = OverflowEventQueue(maxsize=2)

        await queue.enqueue({"id": 1})
        await queue.enqueue({"id": 2})
        await queue.enqueue({"id": 3})

        self.assertEqual((await queue.get())["id"], 2)
        self.assertEqual((await queue.get())["id"], 3)
        self.assertTrue(queue.empty())

    async def test_unbounded_queue_keeps_events(self):
        queue = OverflowEventQueue(maxsize=0)

        await queue.enqueue({"id": 1})
        await queue.enqueue({"id": 2})

        self.assertEqual((await queue.get())["id"], 1)
        self.assertEqual((await queue.get())["id"], 2)


if __name__ == "__main__":
    unittest.main()
