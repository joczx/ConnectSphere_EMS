"""Validation for a Venue Staff decision on a venue booking request.

Kept free of Flask and Supabase imports, like the other schema modules. The
database applies the same rules in review_venue_booking(); checking here as
well means a bad decision is explained field by field and never reaches it.
"""

OUTCOMES = ('approved', 'rejected')
MAX_COMMENTS = 2000


def parse_review(body):
    """Return (data, errors) for an approve or reject decision."""
    if not isinstance(body, dict):
        return {}, {'body': 'Provide a review decision.'}

    data, errors = {}, {}

    outcome = body.get('outcome')
    if outcome not in OUTCOMES:
        errors['outcome'] = 'Choose Approve or Reject.'
    else:
        data['outcome'] = outcome

    comments = body.get('comments')
    if comments is None:
        comments = ''
    if not isinstance(comments, str):
        errors['comments'] = 'Comments must be text.'
        return data, errors

    comments = comments.strip()
    if len(comments) > MAX_COMMENTS:
        errors['comments'] = f'Comments must be {MAX_COMMENTS} characters or fewer.'
    elif outcome == 'rejected' and not comments:
        # The coordinator is told why, so a rejection without a reason would
        # leave them with nothing to act on.
        errors['comments'] = 'A reason is required when rejecting.'
    else:
        data['comments'] = comments

    return data, errors
