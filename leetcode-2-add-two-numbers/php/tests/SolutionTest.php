<?php

require __DIR__ . '/../vendor/autoload.php';

use PHPUnit\Framework\TestCase;
use Leetcode\Solution;
use Leetcode\ListNode;


class SolutionTest extends TestCase {
    // Function to create a linked list from an array (helper function)
    private function createLinkedList($arr) {
        $dummyHead = new ListNode(0);
        $current = $dummyHead;
        foreach ($arr as $value) {
            $current->next = new ListNode($value);
            $current = $current->next;
        }
        return $dummyHead->next;
    }

    // Function to convert linked list to array (helper function)
    private function linkedListToArray($node) {
        $arr = [];
        while ($node !== null) {
            $arr[] = $node->val;
            $node = $node->next;
        }
        return $arr;
    }

    public function testAddTwoNumbersExample1() {
        $l1 = $this->createLinkedList([2, 4, 3]);
        $l2 = $this->createLinkedList([5, 6, 4]);

	$solution = new Solution;
        $result = $solution->addTwoNumbers($l1, $l2);

        $resultArray = $this->linkedListToArray($result);

        $this->assertEquals([7, 0, 8], $resultArray);
    }
    public function testAddTwoNumbersExample2() {
        $l1 = $this->createLinkedList([0]);
        $l2 = $this->createLinkedList([0]);

	$solution = new Solution;
        $result = $solution->addTwoNumbers($l1, $l2);

        $resultArray = $this->linkedListToArray($result);

        $this->assertEquals([0], $resultArray);
    }

    public function testAddTwoNumbersExample3() {
        $l1 = $this->createLinkedList([9, 9, 9, 9, 9, 9, 9]);
        $l2 = $this->createLinkedList([9, 9, 9, 9]);

	$solution = new Solution;
        $result = $solution->addTwoNumbers($l1, $l2);

        $resultArray = $this->linkedListToArray($result);

        $this->assertEquals([8, 9, 9, 9, 0, 0, 0, 1], $resultArray);
    }

    public function testAddTwoNumbersWithDifferentLengths() {
        $l1 = $this->createLinkedList([1, 8]);
        $l2 = $this->createLinkedList([0]);

	$solution = new Solution;
        $result = $solution->addTwoNumbers($l1, $l2);

        $resultArray = $this->linkedListToArray($result);

        $this->assertEquals([1, 8], $resultArray);
    }

    public function testAddTwoNumbersWithCarryOver() {
        $l1 = $this->createLinkedList([9, 9]);
        $l2 = $this->createLinkedList([1]);

	$solution = new Solution;
        $result = $solution->addTwoNumbers($l1, $l2);

        $resultArray = $this->linkedListToArray($result);

        $this->assertEquals([0, 0, 1], $resultArray);
    }
}

