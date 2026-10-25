"""Outcome-only scoring, called after ranking plans are immutable."""
def score_order(order,outcomes,cap=8):
    tried=[];selected=None
    for identity in order[:cap]:
        tried.append(identity)
        if outcomes[identity]['discovery_pass']:
            selected=identity;break
    return {'selected':selected,'attempted':tried,'checks':len(tried),
            'accepted':bool(selected and outcomes[selected]['accepted']),
            'audit_rejected':bool(selected and not outcomes[selected]['accepted'])}
