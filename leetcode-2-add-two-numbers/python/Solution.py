class ListNode:
    def __init__(self, val=0, next=None):
        self.val = val
        self.next = next

class Solution:
    def addTwoNumbers(self, l1, l2):
        dummy_head = ListNode(0)
        current = dummy_head
        carry = 0

        while l1 is not None or l2 is not None:
            x = l1.val if l1 is not None else 0
            y = l2.val if l2 is not None else 0

            total = carry + x + y
            carry = total // 10
            current.next = ListNode(total % 10)
            current = current.next

            if l1 is not None:
                l1 = l1.next
            if l2 is not None:
                l2 = l2.next

        if carry > 0:
            current.next = ListNode(carry)

        return dummy_head.next

# Helper function to create a linked list from a list
def createLinkedList(arr):
    dummy_head = ListNode(0)
    current = dummy_head
    for value in arr:
        current.next = ListNode(value)
        current = current.next
    return dummy_head.next

# Helper function to convert a linked list to a list
def linkedListToList(node):
    result = []
    while node is not None:
        result.append(node.val)
        node = node.next
    return result
