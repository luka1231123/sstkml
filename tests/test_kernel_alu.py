from engine.kernel import alu
from load import load_campaign


def test_every_alu_has_the_minimum_state_needed_for_a_turn():
    kernel = load_campaign("seat", 1).kernel
    assert alu.faults(kernel) == ()


def test_dependent_palace_centres_are_sites_not_alus():
    kernel = load_campaign("seat", 1).kernel
    centres = [site for site in kernel.registry.sites.values()
               if site.function == "palace_centre"]
    assert centres
    assert all(site.settlement in kernel.registry.settlements
               for site in centres)
    assert all(site.id not in kernel.registry.settlements for site in centres)
