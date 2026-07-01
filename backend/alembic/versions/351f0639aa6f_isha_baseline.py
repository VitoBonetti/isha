"""isha_baseline

Revision ID: 351f0639aa6f
Revises: 
Create Date: 2026-07-01 22:29:19.161548

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '351f0639aa6f'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );

        INSERT INTO locations (name) VALUES ('Global');

        CREATE TABLE IF NOT EXISTS countries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            code VARCHAR(10) UNIQUE NOT NULL, 
            name VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS regions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(50) UNIQUE NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS service_lanes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(100) NOT NULL,
            max_concurrent_per_week INTEGER,
            theme_color VARCHAR(20) DEFAULT '#3b82f6',
            default_credits NUMERIC(4,1) DEFAULT 2.0,
            default_duration_weeks INTEGER DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            display_order INTEGER DEFAULT 99
        );

        CREATE TABLE IF NOT EXISTS service_categories (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            service_lane_id UUID REFERENCES service_lanes(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            target_goal INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            github_id VARCHAR(255) UNIQUE, 
            email VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL,
            avatar_url VARCHAR(500),
            role VARCHAR(50) NOT NULL,
            location_id UUID REFERENCES locations(id),
            base_capacity REAL DEFAULT 1.0,
            start_week INTEGER DEFAULT 1,
            start_year INTEGER DEFAULT 2024,
            end_week INTEGER,
            end_year INTEGER
        );

        INSERT INTO users (github_id, email, name, avatar_url, role) 
        VALUES ('99612766', 'vitobonetti@gmail.com', 'Isha', 'https://avatars.githubusercontent.com/u/99612766?v=4', 'admin') 
        ON CONFLICT (email) DO NOTHING;

        CREATE TABLE IF NOT EXISTS raw_assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(500) NOT NULL,
            description TEXT,
            business_critical INTEGER,
            confidentiality_rating INTEGER,
            integrity_rating INTEGER,
            availability_rating INTEGER,
            country_id UUID REFERENCES countries(id),
            service_forecast_id UUID REFERENCES service_lanes(id), 
            category_id UUID REFERENCES service_categories(id)
        );

        CREATE TABLE IF NOT EXISTS assets (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            raw_asset_id UUID REFERENCES raw_assets(id) ON DELETE CASCADE,
            name VARCHAR(500) NOT NULL,
            country_id UUID REFERENCES countries(id),
            service_forecast_id UUID REFERENCES service_lanes(id),
            category_id UUID REFERENCES service_categories(id),
            is_assigned BOOLEAN DEFAULT FALSE,
            UNIQUE (raw_asset_id)
        );

        CREATE TABLE IF NOT EXISTS tests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name VARCHAR(500) NOT NULL,
            service_lane_id UUID REFERENCES service_lanes(id),
            category_id UUID REFERENCES service_categories(id),
            credits_per_week REAL,
            duration_weeks REAL,
            start_week INTEGER,
            start_year INTEGER,
            status VARCHAR(50) DEFAULT 'Not Planned'
        );

        CREATE TABLE IF NOT EXISTS test_assets (
            test_id UUID REFERENCES tests(id) ON DELETE CASCADE,
            asset_id UUID REFERENCES assets(id) ON DELETE CASCADE,
            PRIMARY KEY (test_id, asset_id)
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            test_id UUID REFERENCES tests(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            week_number INTEGER,
            year INTEGER,
            allocated_credits REAL
        );

        CREATE TABLE IF NOT EXISTS events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            event_type VARCHAR(50),
            location_id UUID REFERENCES locations(id),
            start_date DATE,
            end_date DATE
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID REFERENCES users(id) ON DELETE CASCADE,
            message TEXT NOT NULL,
            type VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_read BOOLEAN DEFAULT FALSE
        );
    """)


def downgrade():
    op.execute("""
        DROP TABLE IF EXISTS notifications CASCADE;
        DROP TABLE IF EXISTS events CASCADE;
        DROP TABLE IF EXISTS assignments CASCADE;
        DROP TABLE IF EXISTS test_assets CASCADE;
        DROP TABLE IF EXISTS tests CASCADE;
        DROP TABLE IF EXISTS assets CASCADE;
        DROP TABLE IF EXISTS raw_assets CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
        DROP TABLE IF EXISTS service_categories CASCADE;
        DROP TABLE IF EXISTS service_lanes CASCADE;
        DROP TABLE IF EXISTS regions CASCADE;
        DROP TABLE IF EXISTS countries CASCADE;
        DROP TABLE IF EXISTS locations CASCADE;
    """)