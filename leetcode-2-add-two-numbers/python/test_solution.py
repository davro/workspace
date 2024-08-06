import unittest
from Solution import Solution 
from Solution import createLinkedList
from Solution import linkedListToList

class TestAddTwoNumbers(unittest.TestCase):
    def setUp(self):
        self.sol = Solution()

    def test_add_two_numbers_example1(self):
        l1 = createLinkedList([2, 4, 3])
        l2 = createLinkedList([5, 6, 4])
        result = self.sol.addTwoNumbers(l1, l2)
        self.assertEqual(linkedListToList(result), [7, 0, 8])

    def test_add_two_numbers_example2(self):
        l1 = createLinkedList([0])
        l2 = createLinkedList([0])
        result = self.sol.addTwoNumbers(l1, l2)
        self.assertEqual(linkedListToList(result), [0])

    def test_add_two_numbers_example3(self):
        l1 = createLinkedList([9, 9, 9, 9, 9, 9, 9])
        l2 = createLinkedList([9, 9, 9, 9])
        result = self.sol.addTwoNumbers(l1, l2)
        self.assertEqual(linkedListToList(result), [8, 9, 9, 9, 0, 0, 0, 1])

    def test_add_two_numbers_with_different_lengths(self):
        l1 = createLinkedList([1, 8])
        l2 = createLinkedList([0])
        result = self.sol.addTwoNumbers(l1, l2)
        self.assertEqual(linkedListToList(result), [1, 8])

    def test_add_two_numbers_with_carry_over(self):
        l1 = createLinkedList([9, 9])
        l2 = createLinkedList([1])
        result = self.sol.addTwoNumbers(l1, l2)
        self.assertEqual(linkedListToList(result), [0, 0, 1])

if __name__ == '__main__':
    unittest.main()
