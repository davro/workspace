<?php

// 
// https://leetcode.com/problems/two-sum/solutions/5590941/two-sum/

namespace Leetcode;

use Leetcode\ListNode;

/**
* Definition for a singly-linked list.
* class ListNode {
*     public $val = 0;
*     public $next = null;
*     function __construct($val = 0, $next = null) {
*         $this->val = $val;
*         $this->next = $next;
*     }
* }
*/
class Solution 
{
    /**
     * @param ListNode $l1
     * @param ListNode $l2
     * @return ListNode
     */
    function addTwoNumbers($l1, $l2) {
	$dummyHead = new ListNode(0);
	$current = $dummyHead;
	$carry = 0;
	
	while ($l1 !== null || $l2 !== null) {
	    $x = ($l1 !== null) ? $l1->val : 0;
	    $y = ($l2 !== null) ? $l2->val : 0;
	    
	    $sum = $carry + $x + $y;
	    $carry = intdiv($sum, 10);
	    $current->next = new ListNode($sum % 10);
	    $current = $current->next;
	    
	    if ($l1 !== null) $l1 = $l1->next;
	    if ($l2 !== null) $l2 = $l2->next;
	}
	
	if ($carry > 0) {
	    $current->next = new ListNode($carry);
	}
	
	return $dummyHead->next;
    }

    // Helper function to create a linked list from an array
    function createLinkedList($arr) {
	$dummyHead = new ListNode(0);
	$current = $dummyHead;
	foreach ($arr as $value) {
	    $current->next = new ListNode($value);
	    $current = $current->next;
	}
	return $dummyHead->next;
    }

    // Helper function to print a linked list
    function printLinkedList($node) {
	while ($node !== null) {
	    echo $node->val;
	    if ($node->next !== null) {
		echo " -> ";
	    }
	    $node = $node->next;
	}
	echo "\n";
    }
}

// Example usage:
//$solution = new Solution;

//$l1 = $solution->createLinkedList([2, 4, 3]);
//$l2 = $solution->createLinkedList([5, 6, 4]);

//$result = $solution->addTwoNumbers($l1, $l2);
//$solution->printLinkedList($result); // Output: 7 -> 0 -> 8

