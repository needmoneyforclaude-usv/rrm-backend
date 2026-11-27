from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas import UserUpdate


def test_role_is_normalized_to_uppercase():
    assert UserUpdate(role="lead").role == "LEAD"


def test_unknown_role_is_rejected():
    with pytest.raises(ValidationError):
        UserUpdate(role="BOSS")


def test_affiliation_date_in_future_is_rejected():
    with pytest.raises(ValidationError):
        UserUpdate(affiliation_date=date.today() + timedelta(days=1))


def test_only_sent_fields_are_marked_as_set():
    data = UserUpdate(team_id=None)
    assert data.model_fields_set == {"team_id"}
