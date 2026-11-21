import unittest

from railmancer import cfg, trackhammer, vmfpy


class HeightBlockTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cfg.initialize("railmancer/config.json")
        trackhammer.initialize()

    def setUp(self):

        cfg.CFG["trackhammer_block_mode"] = "height"
        cfg.CFG["trackhammer_height_direction"] = "up"
        cfg.CFG["trackhammer_height_clearance"] = 50
        trackhammer.BlockHorizontal = 1000
        trackhammer.BlockVertical = 1000
        trackhammer.Block_Standoff_Distance = 3000
        trackhammer.clear_occupied()
        vmfpy.Brushes.clear()

    def tearDown(self):

        cfg.CFG["trackhammer_block_mode"] = "layers"
        cfg.CFG["trackhammer_height_direction"] = "up"

    def test_horizontal_cells_match_get_block_ids(self):

        for point in ((0, 0, 10), (1500, -40, 80), (-2200, 2600, -5)):
            from_ids = set()
            for block_id in trackhammer.get_block_ids(point):
                x, y, _z = block_id.split(",")
                from_ids.add((int(x), int(y)))
            self.assertEqual(from_ids, set(trackhammer.horizontal_cells(point)))

    def test_fill_keeps_only_the_top_and_one_record_per_cell(self):

        records = trackhammer.blocks_new([[0, 0, 40], [0, 0, 90]])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 90.0)
        self.assertEqual(trackhammer.Blocks, {})
        cells = [(record[0], record[1]) for record in records]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertTrue(all(record[2] is None for record in records))
        # A lower sample from a later call does not change the stored top
        # and does not add a rollback record.
        self.assertEqual(trackhammer.blocks_new([[0, 0, 20]]), [])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 90.0)

    def test_clearance_up_and_down(self):

        trackhammer.blocks_new([[0, 0, 100]])
        self.assertTrue(trackhammer.are_points_blocked([[0, 0, 149]]))
        self.assertFalse(trackhammer.are_points_blocked([[0, 0, 150]]))
        self.assertFalse(trackhammer.are_points_blocked([[8000, 8000, 0]]))

        trackhammer.clear_occupied()
        cfg.CFG["trackhammer_height_direction"] = "down"
        trackhammer.blocks_new([[0, 0, 100]])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 100.0)
        self.assertTrue(trackhammer.are_points_blocked([[0, 0, 51]]))
        self.assertFalse(trackhammer.are_points_blocked([[0, 0, 50]]))
        # A higher rail does not raise the stored floor.
        self.assertEqual(trackhammer.blocks_new([[0, 0, 180]]), [])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 100.0)
        lowered = trackhammer.blocks_new([[0, 0, 40]])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 40.0)
        self.assertEqual(lowered[0][2], 100.0)

    def test_samples_along_the_segment_not_just_the_ends(self):

        trackhammer.blocks_new([[5000, 0, 0]])
        ends = [[0, 0, 0], [10000, 0, 0]]
        self.assertFalse(trackhammer.are_points_blocked(ends))
        points = trackhammer.get_block_points_from_nodes(
            ([0, 0, 0], "0fw", 0, False),
            ([10000, 0, 0], "0fw", 0, False),
        )
        self.assertGreater(len(points), 2)
        self.assertTrue(trackhammer.are_points_blocked(points))

    def test_rollback_restores_prior_when_newest_is_removed_first(self):

        older = trackhammer.blocks_new([[0, 0, 100]])
        newer = trackhammer.blocks_new([[0, 0, 250]])
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 250.0)
        prior = {(record[0], record[1]): record[2] for record in newer}
        self.assertEqual(prior[(0, 0)], 100.0)

        trackhammer.blocks_remove(newer)
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 100.0)
        trackhammer.blocks_remove(older)
        self.assertNotIn((0, 0), trackhammer.HeightTable)

    def test_removing_the_earlier_step_first_wipes_the_newer_top(self):

        # backtrack never does this. It is here so the failure mode stays
        # visible: the record only knows the value it overwrote, not who
        # wrote on top of it afterwards.
        older = trackhammer.blocks_new([[0, 0, 100]])
        newer = trackhammer.blocks_new([[0, 0, 250]])
        trackhammer.blocks_remove(older)
        self.assertNotIn((0, 0), trackhammer.HeightTable)
        trackhammer.blocks_remove(newer)
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 100.0)

    def test_standoff_commits_only_track_far_behind_the_head(self):

        far = self._step(0, [[0, 0, 10]])
        mid = self._step(2000, [[8000, 0, 40]])
        near = self._step(4000, [[16000, 0, 70]])
        head = self._step(9000, [[24000, 0, 90]])
        steps = [far, mid, near, head]

        cursor = trackhammer.update_blocks(steps, 0)
        self.assertEqual(cursor, 2)
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 10.0)
        self.assertIn((8, 0), trackhammer.HeightTable)
        self.assertNotIn((16, 0), trackhammer.HeightTable)
        self.assertNotIn((24, 0), trackhammer.HeightTable)
        self.assertTrue(mid["blocks_added"])
        self.assertEqual(near["blocks_added"], [])
        self.assertTrue(trackhammer.are_points_blocked(mid["points"]))
        self.assertFalse(trackhammer.are_points_blocked(near["points"]))

        # Drop the head. update_blocks walks backward from the commit cursor
        # and only releases a committed step once the head is within the
        # standoff of the step before it. Mid stays reserved here: the head
        # is still 4000 ahead of far, which is outside the 3000 standoff.
        steps.pop()
        trackhammer.blocks_remove(head["blocks_added"])
        cursor = trackhammer.update_blocks(steps, min(cursor, len(steps) - 1))
        self.assertIn((8, 0), trackhammer.HeightTable)

        # Pop near as well. The head is now mid, 2000 ahead of far, inside
        # the standoff, so the backward walk restores mid's cells.
        steps.pop()
        trackhammer.blocks_remove(near["blocks_added"])
        cursor = trackhammer.update_blocks(steps, 1)
        self.assertEqual(cursor, 0)
        self.assertEqual(mid["blocks_added"], [])
        self.assertNotIn((8, 0), trackhammer.HeightTable)
        self.assertEqual(trackhammer.HeightTable[(0, 0)], 10.0)

        # Popping far itself is what backtrack does to the last step: restore
        # the prior recorded on that step, which was an empty cell.
        trackhammer.blocks_remove(far["blocks_added"])
        self.assertNotIn((0, 0), trackhammer.HeightTable)

    def test_indicator_is_one_slab_per_cell_at_the_stored_height(self):

        trackhammer.BlockVertical = 100
        trackhammer.blocks_new([[0, 0, 250]])
        trackhammer.display_blocks_in_vmf()
        self.assertEqual(len(vmfpy.Brushes), len(trackhammer.HeightTable))
        self.assertGreater(len(vmfpy.Brushes), 0)
        for brush in vmfpy.Brushes:
            self.assertEqual(brush[6], "dev/dev_measurewall01d")
            # Up mode fills from the map floor up through the stored rail
            # plus one block layer: z0 is fixed, z1 is stored + BlockVertical.
            self.assertEqual(brush[4], -16320)
            self.assertEqual(brush[5], 350.0)
            self.assertEqual(brush[1] - brush[0], 1000)

        vmfpy.Brushes.clear()
        cfg.CFG["trackhammer_height_direction"] = "down"
        trackhammer.clear_occupied()
        trackhammer.blocks_new([[0, 0, 250]])
        trackhammer.display_blocks_in_vmf()
        # Down mode hangs from the stored rail minus one block layer and
        # fills up to the map ceiling.
        self.assertEqual(vmfpy.Brushes[0][4], 150.0)
        self.assertEqual(vmfpy.Brushes[0][5], 16320)

    def test_layers_setting_still_uses_height_mode(self):

        # height_mode_enabled() is fixed on. trackhammer_block_mode is not
        # read, so asking for layers still reserves height records.
        cfg.CFG["trackhammer_block_mode"] = "layers"
        self.assertTrue(trackhammer.height_mode_enabled())
        added = trackhammer.blocks_new([[0, 0, 0]])
        self.assertTrue(added)
        for record in added:
            self.assertEqual(len(record), 3)
            self.assertIsNone(record[2])
        self.assertTrue(trackhammer.HeightTable)
        self.assertEqual(len(trackhammer.HeightTable), len(added))
        self.assertEqual(trackhammer.Blocks, {})
        trackhammer.display_blocks_in_vmf()
        self.assertEqual(len(vmfpy.Brushes), len(trackhammer.HeightTable))
        self.assertGreater(len(vmfpy.Brushes), 0)
        for brush in vmfpy.Brushes:
            self.assertEqual(brush[6], "dev/dev_measurewall01d")
            self.assertEqual(brush[4], -16320)

    def _step(self, length, points):

        return {
            "length": length,
            "points": points,
            "blocks_added": [],
        }


if __name__ == "__main__":
    unittest.main()
