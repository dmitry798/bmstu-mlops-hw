import asyncio
import unittest
from app.core import Admission, Rejected, PrefixCache, classify, bucket_quantile, validate_payload

class CoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_bounded_queue_rejects_then_recovers(self):
        gate=Admission(1,1)
        await gate.acquire()
        pending=asyncio.create_task(gate.acquire());await asyncio.sleep(.01)
        self.assertEqual((gate.running,gate.waiting),(1,1))
        with self.assertRaises(Rejected):await gate.acquire()
        await gate.release();await pending
        self.assertEqual((gate.running,gate.waiting),(1,0))
        await gate.release();self.assertEqual(gate.running,0)
    async def test_cancelled_waiter_never_leaks_capacity(self):
        gate=Admission(1,2);await gate.acquire()
        pending=asyncio.create_task(gate.acquire());await asyncio.sleep(.01);pending.cancel()
        with self.assertRaises(asyncio.CancelledError):await pending
        self.assertEqual(gate.waiting,0)
        await gate.release();await gate.acquire();await gate.release()
    def test_prefix_lru_is_local_and_bounded(self):
        first,second=PrefixCache(2),PrefixCache(2)
        self.assertFalse(first.lookup('a'));self.assertTrue(first.lookup('a'))
        self.assertFalse(second.lookup('a'))
        first.lookup('b');first.lookup('a');first.lookup('c')
        self.assertFalse(first.lookup('b'));self.assertLessEqual(len(first.entries),2)
    def test_partial_200_is_aborted_not_success(self):
        self.assertEqual(classify(200,False,False),'aborted')
        self.assertEqual(classify(200,True,False),'completed')
        self.assertEqual(classify(429,False,False),'rejected')
        self.assertEqual(classify(200,False,True),'expired')
        self.assertEqual(classify(0,False,False),'error')
    def test_classic_histogram_quantile_uses_cumulative_buckets(self):
        self.assertAlmostEqual(bucket_quantile([(0.1,5),(.2,10),(float('inf'),10)],.95),.19)
        self.assertIsNone(bucket_quantile([(.1,0),(float('inf'),0)],.95))
    def test_invalid_payload_rejected_before_computation(self):
        for payload in [{'messages':[]},{'messages':[{'role':'user','content':'x'}],'chunks':True},{'messages':[{'role':'user','content':'x'}],'chunks':65}]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):validate_payload(payload)
        valid=validate_payload({'messages':[{'role':'user','content':'DIALOG_A_CONTROL'}]})
        self.assertIn('DIALOG_A_CONTROL',valid['messages'][0]['content'])
