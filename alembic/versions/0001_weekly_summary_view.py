"""Create weekly_timesheet_summary view.

Revision ID: 0001
Revises:
Create Date: 2026-06-06
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE VIEW weekly_timesheet_summary AS
        SELECT
            te.user_id,
            au.email                                         AS user_email,
            au.first_name || ' ' || au.last_name            AS full_name,
            p.id                                             AS project_id,
            p.name                                           AS project_name,
            c.name                                           AS client_name,
            DATE_TRUNC('week', te.date)::date               AS week_start,
            DATE_TRUNC('week', te.date)::date + 6           AS week_end,
            SUM(te.hours)                                    AS total_hours,
            SUM(te.hours * COALESCE(te.hourly_rate, p.default_hourly_rate, 0)) AS total_amount,
            COUNT(te.id)                                     AS entry_count
        FROM timesheets_timeentry te
        JOIN auth_user au ON au.id = te.user_id
        JOIN timesheets_project p ON p.id = te.project_id
        LEFT JOIN timesheets_client c ON c.id = p.client_id
        WHERE te.is_deleted = FALSE
        GROUP BY
            te.user_id, au.email, au.first_name, au.last_name,
            p.id, p.name, c.name,
            DATE_TRUNC('week', te.date)
        ORDER BY week_start DESC, full_name, project_name;
        """
    )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION update_modified_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS weekly_timesheet_summary;")
    op.execute("DROP FUNCTION IF EXISTS update_modified_column();")
