from src.backoffice.persistence.database import Base
from sqlalchemy import Column, Integer, Float, String, TIMESTAMP, Boolean, Time

from src.backoffice.forecasts.models import ForecastSchedule


class InarizSteamProd(Base):
    __tablename__ = "inariz_steam_prod"

    measured_at_utc = Column(TIMESTAMP(timezone=True), primary_key=True)
    steam_production_m3_h = Column(Float, nullable=False)
    unit = Column(String, server_default="m3/h")


class InarizSteamForecast(Base):
    __tablename__ = "inariz_steam_forecast"

    measured_at_utc = Column(TIMESTAMP(timezone=True), primary_key=True)
    steam_production_m3_h = Column(Float, nullable=False)
    unit = Column(String, server_default="m3/h")


class ForecastScheduleORM(
    Base
):  # c'est peut-être risqué de mettre exactement le même nom
    __tablename__ = "forecast_schedule"

    schedule_id = Column(String, primary_key=True, nullable=False)
    site = Column(String, nullable=False)
    model = Column(String, nullable=False)
    n_splits = Column(Integer, nullable=False)
    gap = Column(Integer, nullable=False)
    test_size = Column(Integer, nullable=False)
    active = Column(Boolean, nullable=False)
    trigger_time = Column(Time, nullable=False)
    timezone = Column(String, nullable=False)
    last_triggered_at = Column(TIMESTAMP, nullable=True)

    # mapper function
    def to_domain_schedule(self) -> ForecastSchedule:
        return ForecastSchedule(
            schedule_id=self.schedule_id,
            site=self.site,
            model=self.model,  # cast if needed
            n_splits=self.n_splits,
            gap=self.gap,
            test_size=self.test_size,
            active=self.active,
            trigger_time=self.trigger_time,
            timezone=self.timezone,
            last_triggered_at=self.last_triggered_at,
        )


# mapper function
def to_orm_schedule(domain_schedule: ForecastSchedule) -> ForecastScheduleORM:
    return ForecastScheduleORM(
        schedule_id=domain_schedule.schedule_id,
        site=domain_schedule.site,
        model=domain_schedule.model,
        n_splits=domain_schedule.n_splits,
        gap=domain_schedule.gap,
        test_size=domain_schedule.test_size,
        active=domain_schedule.active,
        trigger_time=domain_schedule.trigger_time,
        timezone=domain_schedule.timezone,
        last_triggered_at=domain_schedule.last_triggered_at,
    )
