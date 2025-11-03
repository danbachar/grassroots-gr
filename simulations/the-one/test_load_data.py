# Unit tests
import unittest
from load_data import Topology

class TestTopology(unittest.TestCase):

    def test_add_connection_nonexisting_source_throws(self):
        """Test that adding a connection with a non-existing source node raises an error"""
        topology = Topology([])
        with self.assertRaises(KeyError) as err:
            topology.add_connection("nonexistent_node", "node2")
        self.assertEqual(err.exception.args[0], f"Source node 'nonexistent_node' not in topology.")

    def test_add_connection_nonexisting_target_throws(self):
        """Test that adding a connection with a non-existing target node raises an error"""
        topology = Topology(['1'])
        with self.assertRaises(KeyError) as err:
            topology.add_connection("1", "2")
        self.assertEqual(err.exception.args[0], f"Target node '2' not in topology.")

    def test_add_connection_creates_one_bidirectional_link(self):
        """Test that adding a single connection creates a single bidirectional link"""
        topology = Topology(["node1", "node2"])
        topology.add_connection("node1", "node2")
        self.assertEqual(len(topology.connections), 2)

        node1_neighbors = topology.connections["node1"]
        self.assertEqual(len(node1_neighbors), 1)

        node2_neighbors = topology.connections["node2"]
        self.assertEqual(len(node2_neighbors), 1)
        self.assertIn("node1", node2_neighbors)

    def test_add_duplicate_connection_does_not_change(self):
        """Test that adding a duplicate connection does not change the topology"""
        topology = Topology(["node1", "node2"])
        topology.add_connection("node1", "node2")
        topology.add_connection("node1", "node2") # duplicate
        topology.add_connection("node2", "node1") # flipped
        self.assertEqual(len(topology.connections), 2)

        [node1, node2] = topology.connections.keys()
        node1_neighbors = topology.connections[node1]
        node2_neighbors = topology.connections[node2]
        self.assertEqual(len(node1_neighbors), 1)
        self.assertEqual(len(node2_neighbors), 1)
        self.assertIn("node2", node1_neighbors)
        self.assertIn("node1", node2_neighbors)

    def test_remove_connection_nonexisting_source_throws(self):
        """Test that removing a connection with a non-existing source node raises an error"""
        topology = Topology([])
        with self.assertRaises(KeyError) as err:
            topology.remove_connection("nonexistent_node", "node2")
        self.assertEqual(err.exception.args[0], f"Source node 'nonexistent_node' not in topology.")

    def test_remove_connection_nonexisting_target_throws(self):
        """Test that removing a connection with a non-existing target node raises an error"""
        topology = Topology(['1'])
        with self.assertRaises(KeyError) as err:
            topology.remove_connection("1", "2")
        self.assertEqual(err.exception.args[0], f"Target node '2' not in topology.")

    def test_remove_connection_removes_one_bidirectional_link(self):
        """Test that removing a single connection removes a single link"""
        topology = Topology(["node1", "node2"])
        topology.add_connection("node1", "node2")
        self.assertEqual(len(topology.connections), 2)
        self.assertEqual(topology.get_number_of_links(), 1)

        topology.remove_connection("node1", "node2")
        self.assertEqual(len(topology.connections), 2)

        empty_set: set[str] = set()
        node1_neighbors = topology.connections["node1"]
        self.assertEqual(node1_neighbors, empty_set)

        node2_neighbors = topology.connections["node2"]
        self.assertEqual(node2_neighbors, empty_set)

    def test_remove_connection_removes_exactly_one_bidirectional_link(self):
        """Test that removing a single connection removes one single link"""
        topology = Topology(["node1", "node2, node3"])
        topology.add_connection("node1", "node2")
        topology.add_connection("node1", "node3")
        self.assertEqual(len(topology.connections), 3) # connections is as big as the number of nodes
        self.assertEqual(topology.get_number_of_links(), 2) # links is number of unique connections

        topology.remove_connection("node1", "node2")
        self.assertEqual(len(topology.connections), 3)
        self.assertEqual(topology.get_number_of_links(), 1)

        empty_set: set[str] = set()
        node1_neighbors = topology.connections["node1"]
        self.assertEqual(node1_neighbors, empty_set)

        node2_neighbors = topology.connections["node2"]
        self.assertEqual(node2_neighbors, set("node3"))
    def test_get_number_of_links_empty_topology(self):
        """Test that an empty topology has 0 links"""
        topology = Topology([])
        self.assertEqual(topology.get_number_of_links(), 0)
    
    def test_get_number_of_links_single_connection(self):
        """Test that a single connection counts as 1 link"""
        topology = Topology(["node1", "node2"])
        topology.add_connection("node1", "node2")
        topology.add_connection("node2", "node1")
        self.assertEqual(topology.get_number_of_links(), 1)

    def test_get_number_of_links_duplicate_single_connection(self):
        """Test that a connection s->t and t->s counts as 1 link (s<->t)"""
        topology = Topology(["node1", "node2"])
        topology.add_connection("node1", "node2")
        topology.add_connection("node2", "node1")
        self.assertEqual(topology.get_number_of_links(), 1)

    def test_get_number_of_links_two_connections(self):
        """Test that a two connections count as two link"""
        topology = Topology(["1", "2", "3"])
        topology.add_connection("1", "2")
        topology.add_connection("2", "3")
        self.assertEqual(topology.get_number_of_links(), 2)

    def test_get_number_of_links_three_connections(self):
        """Test that a three connections count as three links"""
        topology = Topology(["1", "2", "3"])
        topology.add_connection("1", "2")
        topology.add_connection("2", "3")
        topology.add_connection("1", "3")
        self.assertEqual(topology.get_number_of_links(), 3)

if __name__ == '__main__':
    unittest.main()
