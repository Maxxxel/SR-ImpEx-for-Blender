"""Deterministic artist damage pattern; not a gameplay hit-position simulator."""


def scratch_factor(damage):
    # CDrwDestructibleGrid::AdjustTotalHealth (100BFD00), globals
    # kfScratchMultiplier=1.4 and kfScratchMin=.1 in foundationr.dll.
    return min(.9, max(0., float(damage)) * 1.4)


def damage_states(cells, damage):
    """Consume each cell down to 25% health, with S2 at 50%; crush at 100%.

    The thresholds follow the health-taking constructor and DistributeDamage.
    Ascending cell order is an explicit preview policy. Gameplay chooses its
    starting cell from the hit position and recursively visits its neighbours.
    """
    cells=sorted(set(cells));damage=max(0., min(1., float(damage)))
    if damage>=1.:return {cell:3 for cell in cells}
    remaining=damage*len(cells);result={}
    for cell in cells:
        used=min(.75,remaining)
        result[cell]=2 if used>=.5 else 0
        remaining=max(0.,remaining-used)
    return result
