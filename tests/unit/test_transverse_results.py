import numpy as np
import pytest
import xarray as xr

from osdagbridge.core.bridge_types.plate_girder import plot_generator as pg
from osdagbridge.core.bridge_types.plate_girder import results_data as rd

XS = [0.0, 5.0, 10.0]
ZS = [0.0, 2.0, 4.0]


def _grid():
    nodes, members = {}, {}
    for i, x in enumerate(XS):
        for j, z in enumerate(ZS):
            nodes[i * 3 + j + 1] = (x, 0.0, z)
    tag = 1
    for i in range(3):
        for j in range(2):
            members[tag] = [i * 3 + j + 1, i * 3 + j + 2]   # across the width
            tag += 1
    for j in range(3):
        for i in range(2):
            members[tag] = [i * 3 + j + 1, (i + 1) * 3 + j + 1]   # along the span
            tag += 1
    return nodes, members


def _dataset(nodes, members, forces=None):
    force_comps = ["Vx_i", "Vy_i", "Vz_i", "Mx_i", "My_i", "Mz_i", "Vx_j", "Vy_j", "Vz_j", "Mx_j", "My_j", "Mz_j"]
    comps = force_comps + ["x", "y", "z"]   # one shared Component axis, as in the ospgrillage dataset
    data = np.full((len(members), len(comps)), np.nan)
    data[:, :len(force_comps)] = 0.0
    for (tag, comp), value in (forces or {}).items():
        data[list(members).index(tag), comps.index(comp)] = value
    disp = np.full((len(nodes), len(comps)), np.nan)
    disp[:, comps.index("y")] = -0.002
    disp[:, comps.index("x")] = disp[:, comps.index("z")] = 0.0
    return xr.Dataset({
        "forces": (("Element", "Component"), data),
        "displacements": (("Node", "Component"), disp),
    }, coords={"Element": list(members), "Component": comps, "Node": list(nodes)})


@pytest.fixture
def grid():
    nodes, members = _grid()
    return nodes, members


def test_classify_splits_by_direction(grid):
    nodes, members = grid
    longitudinal, transverse = rd.classify_members(nodes, members)
    assert sorted(transverse) == [1, 2, 3, 4, 5, 6]
    assert sorted(longitudinal) == [7, 8, 9, 10, 11, 12]


def test_chains_are_ordered_lines_across_width(grid):
    nodes, members = grid
    chains = rd.transverse_chains(nodes, members)
    assert [len(c) for c in chains] == [2, 2, 2]
    assert [nodes[members[c[0]][0]][0] for c in chains] == XS


def test_chain_follows_nodes_when_element_is_reversed(grid):
    nodes, members = grid
    members[1] = [2, 1]
    assert rd.transverse_chains(nodes, members)[0] == [1, 2]


def test_chains_follow_skewed_lines(grid):
    nodes, members = grid
    for n in (3, 6, 9):
        x, y, z = nodes[n]
        nodes[n] = (x + 1.0, y, z)
    assert [len(c) for c in rd.transverse_chains(nodes, members)] == [2, 2, 2]


def test_bending_maps_to_global_mx(grid):
    nodes, members = grid
    ds = _dataset(nodes, members, {(1, "Mx_i"): 3000.0, (1, "Mx_j"): -1000.0, (2, "Mx_i"): 1000.0, (2, "Mx_j"): 0.0})
    line = rd.extract_transverse_results(ds, "Mz", nodes, members)[0]
    assert line["values"].tolist() == [3.0, 1.0, 0.0]


def test_shear_and_axial_use_their_own_components(grid):
    nodes, members = grid
    ds = _dataset(nodes, members, {(1, "Vy_i"): 2000.0, (1, "Vz_i"): 500.0})
    assert rd.extract_transverse_results(ds, "Fy", nodes, members)[0]["values"][0] == 2.0
    assert rd.extract_transverse_results(ds, "Fx", nodes, members)[0]["values"][0] == 0.5


def test_displacement_in_mm_with_sag_negative_sign_flipped(grid):
    nodes, members = grid
    ds = _dataset(nodes, members)
    values = rd.extract_transverse_results(ds, "Dy", nodes, members)[0]["values"]
    assert values.tolist() == pytest.approx([2.0, 2.0, 2.0])


@pytest.mark.parametrize("key", ["Fx", "Fy", "Fz", "Mx", "My", "Mz", "Dx", "Dy", "Dz"])
def test_figure_builds_for_every_key(grid, key):
    nodes, members = grid
    ds = _dataset(nodes, members, {(1, "Vy_i"): 1000.0})
    fig, summary = pg.build_figure_transverse(ds, key, nodes, members)
    assert fig.axes and "Transverse" in summary
