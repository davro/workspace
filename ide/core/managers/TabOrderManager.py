"""
Tracks tab access order for MRU (Most Recently Used) navigation
"""


class TabOrderManager:
    """
    Manages tab access order for MRU navigation
    
    Tracks which tabs are accessed and maintains recently-used order
    """
    
    def __init__(self):
        """Initialize tab order manager"""
        self.access_order = []  # List of tab indices in MRU order
    
    def record_access(self, tab_index):
        """
        Record that a tab was accessed
        
        Args:
            tab_index: Index of the accessed tab
        """
        # Remove from list if already present
        if tab_index in self.access_order:
            self.access_order.remove(tab_index)
        
        # Add to front (most recent)
        self.access_order.insert(0, tab_index)
    
    def remove_tab(self, tab_index):
        """
        Remove a tab from tracking when it's closed
        
        Args:
            tab_index: Index of the closed tab
        """
        if tab_index in self.access_order:
            self.access_order.remove(tab_index)
        
        # Adjust indices for tabs after the removed one
        self.access_order = [
            idx - 1 if idx > tab_index else idx 
            for idx in self.access_order
        ]
    
    def get_recent_order(self, current_index):
        """
        Get tabs in recently-used order, with current tab first
        
        Args:
            current_index: Current tab index
            
        Returns:
            List of tab indices in MRU order
        """
        # Start with current tab
        order = [current_index]
        
        # Add other tabs in access order
        for idx in self.access_order:
            if idx != current_index and idx not in order:
                order.append(idx)
        
        return order
    
    def clear(self):
        """Clear all tracking"""
        self.access_order.clear()

