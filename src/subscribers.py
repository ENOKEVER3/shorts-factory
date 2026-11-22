"""Daily subscriber observations carried in private Actions artifacts, never in git."""
def count(stats):
    if stats.get('hiddenSubscriberCount') or 'subscriberCount' not in stats:
        return None
    return int(stats['subscriberCount'])

def record(history, channel_id, value, timestamp):
    if history.get('channel_id') not in (None, channel_id):
        raise ValueError('Subscriber history belongs to another channel')
    points = list(history.get('points', []))
    if value is not None:
        day = timestamp[:10]
        points = [p for p in points if p['at'][:10] != day]
        points.append({'at': timestamp, 'count': value})
    return {'channel_id': channel_id, 'points': sorted(points, key=lambda p: p['at'])}