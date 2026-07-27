"""
SQLite database through SQLAlchemy.
Each class represents a database table, while relationships connect records
that belong to the same user. Validation constraints are also defined here so
important data rules are enforced by the database as well as by the routes.
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy


# Create the shared SQLAlchemy object. main.py imports this object and connects
# it to the Flask application using db.init_app(app).
db = SQLAlchemy()


def utc_now():
    """Return the current UTC time without timezone information.

    SQLite does not preserve timezone information consistently, so all
    database datetimes are stored as timezone-naive UTC values. Using one
    helper keeps timestamps consistent across study sessions, subjects, and
    notepad items.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(db.Model):
    """Store account details and connect each user to their personal data."""

    __tablename__ = "users"

    # A numerical primary key uniquely identifies each account. Related tables
    # store this value in their user_id foreign-key columns.
    user_id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Both usernames and email addresses must be unique so they can safely be
    # used to identify an account during registration and login.
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

    # Only the securely generated password hash is stored. The user's original
    # password must never be saved directly in the database.
    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    # This flag records whether the user has completed the required subject
    # onboarding step after creating their account.
    subject_setup_completed = db.Column(
        db.Boolean,
        nullable=False,
        default=False
    )

    # These one-to-many relationships provide convenient access to all records
    # owned by a user, such as user.study_sessions. "delete-orphan" ensures
    # dependent records are removed if their parent user is deleted.

    #1 user can have multiple study sessions
    study_sessions = db.relationship(
        "StudySession",
        back_populates="user",
        cascade="all, delete-orphan"
    )

    subjects = db.relationship(
        "Subject",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="Subject.subject_name"
    )
    notepad_items = db.relationship(
        "NotepadItem",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="NotepadItem.notepad_item_id"
    )

    def __repr__(self):
        """Return a concise description that is useful during debugging."""
        return f"<User {self.username}>"


class Subject(db.Model):
    """Store the subjects a user can assign to their study sessions."""

    __tablename__ = "subjects"

    subject_id = db.Column(
        db.Integer,
        primary_key=True
    )

    # The foreign key links the subject to its owner. The index improves
    # queries that repeatedly retrieve one user's subjects.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # subject_name is shown to the user. normalised_name stores a cleaned
    # version used to prevent duplicates that differ only by spacing or case.
    subject_name = db.Column(
        db.String(100),
        nullable=False
    )
    normalised_name = db.Column(
        db.String(100),
        nullable=False
    )

    # Deactivating a subject removes it from future selection without deleting
    # its historical study sessions or past analytics.
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    # created_at records when the subject was added. updated_at is refreshed
    # automatically whenever SQLAlchemy updates the record.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now
    )

    # back_populates creates both directions of each connection:
    # subject.user and subject.study_sessions.
    user = db.relationship(
        "User",
        back_populates="subjects"
    )
    study_sessions = db.relationship(
        "StudySession",
        back_populates="subject"
    )

    __table_args__ = (
        # A user cannot create two subjects with the same normalised name.
        # Different users may still use the same subject names.
        db.UniqueConstraint(
            "user_id",
            "normalised_name",
            name="unique_subject_name_per_user"
        ),
        # This database-level rule rejects empty or whitespace-only names.
        db.CheckConstraint(
            "length(trim(subject_name)) > 0",
            name="subject_name_cannot_be_empty"
        ),
    )

    def __repr__(self):
        """Return the subject's identifier and display name for debugging."""
        return (
            f"<Subject {self.subject_id}: "
            f"{self.subject_name}>"
        )


class StudySession(db.Model):
    """Store planned and completed study time for the timer and analytics."""

    __tablename__ = "study_sessions"

    study_session_id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Every study session belongs to one user. Indexing this foreign key makes
    # per-user session history and analytics queries more efficient.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )

    # A session may be uncategorised, so subject_id is nullable. SET NULL keeps
    # the session and its study time if its subject record is deleted.
    subject_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "subjects.subject_id",
            ondelete="SET NULL"
        ),
        nullable=True,
        index=True
    )

    # The timer stores durations in seconds for accurate countdowns and partial
    # session tracking. Planned time is selected before starting, while actual
    # time records how long the user ultimately studied.
    planned_duration_seconds = db.Column(
        db.Integer,
        nullable=False
    )
    actual_duration_seconds = db.Column(
        db.Integer,
        nullable=False,
        default=0
    )

    # Timestamps allow the application to restore an active timer and calculate
    # daily or monthly study totals. ended_at remains empty while active.
    started_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now
    )
    ended_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # The status describes how the session ended, such as active, completed,
    # ended_early, cancelled_navigation, or replaced.
    status = db.Column(
        db.String(30),
        nullable=False,
        default="active"
    )

    # These relationships allow routes to move between a session, its owner,
    # and its optional subject without manually joining tables each time.
    user = db.relationship(
        "User",
        back_populates="study_sessions"
    )
    subject = db.relationship(
        "Subject",
        back_populates="study_sessions"
    )

    __table_args__ = (
        # Enforce the timer's allowed range at database level: at least
        # 15 minutes (900 seconds) and at most 12 hours (43,200 seconds).
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
        """Return the session identifier and current status for debugging."""
        return (
            f"<StudySession "
            f"{self.study_session_id}: {self.status}>"
        )


class DailyStudyGoal(db.Model):
    """Store one personalised study-time goal per user for each date."""

    __tablename__ = "daily_study_goals"

    goal_id = db.Column(
        db.Integer,
        primary_key=True
    )

    # The indexed user_id supports frequent goal lookups for the logged-in user.
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
        # A user can have only one goal for a particular calendar date.
        db.UniqueConstraint(
            "user_id",
            "goal_date",
            name="unique_user_daily_goal"
        ),
        # Goals follow the same 15-minute selection system as the timer and
        # must stay between 15 minutes and 12 hours.
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
        """Return the user, date, and goal length for debugging."""
        return (
            f"<DailyStudyGoal "
            f"user={self.user_id}, "
            f"date={self.goal_date}, "
            f"minutes={self.goal_minutes}>"
        )


class NotepadItem(db.Model):
    """Store an individual item in a user's personal dashboard notepad."""

    __tablename__ = "notepad_items"

    notepad_item_id = db.Column(
        db.Integer,
        primary_key=True
    )

    # Each item is privately associated with its owner. The index speeds up
    # loading the complete notepad whenever the dashboard opens.
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.user_id"),
        nullable=False,
        index=True
    )
    item_text = db.Column(
        db.Text,
        nullable=False
    )

    # These timestamps record when the item was created and last edited.
    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=utc_now,
        onupdate=utc_now
    )

    user = db.relationship(
        "User",
        back_populates="notepad_items"
    )

    __table_args__ = (
        # Prevent empty or whitespace-only items from being stored, even if
        # application-level validation is accidentally bypassed.
        db.CheckConstraint(
            "length(trim(item_text)) > 0",
            name="notepad_item_cannot_be_empty"
        ),
    )

    def __repr__(self):
        """Return the item's identifier and owner for debugging."""
        return (
            f"<NotepadItem "
            f"{self.notepad_item_id}: "
            f"user={self.user_id}>"
        )