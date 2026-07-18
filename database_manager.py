from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


def utc_now():
    """
    Return the current UTC time without timezone information.

    SQLite does not preserve timezone information consistently,
    so all database datetimes will be stored as UTC.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    user_email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    study_sessions = db.relationship(
        "StudySession",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.username}>"


class StudySession(db.Model):
    __tablename__ = "study_sessions"

    study_session_id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    planned_duration_seconds = db.Column(
        db.Integer,
        nullable=False
    )

    actual_duration_seconds = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    started_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now
    )

    ended_at = db.Column(
        db.DateTime,
        nullable=True
    )

    status = db.Column(
        db.String(30),
        nullable=False,
        default="active"
    )

    user = db.relationship(
        "User",
        back_populates="study_sessions"
    )

    __table_args__ = (
        db.CheckConstraint(
            "planned_duration_seconds >= 900",
            name="minimum_study_duration"
        ),
        db.CheckConstraint(
            "planned_duration_seconds <= 43200",
            name="maximum_study_duration"
        ),
    )

    def __repr__(self):
        return (
            f"<StudySession "
            f"{self.study_session_id}: {self.status}>"
        )
    

class DailyStudyGoal(db.Model):
    __tablename__ = "daily_study_goals"

    goal_id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    goal_date = db.Column(
        db.Date,
        nullable=False
    )

    goal_minutes = db.Column(
        db.Integer,
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "goal_date",
            name="unique_user_daily_goal"
        ),
        db.CheckConstraint(
            "goal_minutes >= 15",
            name="minimum_daily_goal"
        ),
        db.CheckConstraint(
            "goal_minutes <= 720",
            name="maximum_daily_goal"
        ),
        db.CheckConstraint(
            "goal_minutes % 15 = 0",
            name="daily_goal_interval"
        ),
    )

    def __repr__(self):
        return (
            f"<DailyStudyGoal "
            f"user={self.user_id}, "
            f"date={self.goal_date}, "
            f"minutes={self.goal_minutes}>"
        )