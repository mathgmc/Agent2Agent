from datetime import date, datetime, timedelta
from typing import Dict

# In-memory database for jam session schedules, mapping date to a dictionary of time slots and party names
JAM_SPOT_SCHEDULE: Dict[str, Dict[str, str]] = {}

def generate_friends_schedule():
    """Generates a schedule for the jam session for the next 7 days."""
    global JAM_SPOT_SCHEDULE
    today = date.today()
    possible_times = [f"{h:02}:00" for h in range(8, 21)]  # 8 AM to 8 PM

    for i in range(7):
        current_date = today + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        JAM_SPOT_SCHEDULE[date_str] = {time: "unknown" for time in possible_times}


# Initialize the schedule when the module is loaded
generate_friends_schedule()


def list_jam_spot_availabilities(date: str) -> dict:
    """
    Lists the available and booked time slots for a jam session on a given date.

    Args:
        date: The date to check, in YYYY-MM-DD format.

    Returns:
        A dictionary with the status and the detailed schedule for the day.
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid date format. Please use YYYY-MM-DD.",
        }

    daily_schedule = JAM_SPOT_SCHEDULE.get(date)
    if not daily_schedule:
        return {
            "status": "success",
            "message": f"The jam spot is not open on {date}.",
            "schedule": {},
        }

    available_slots = [
        time for time, party in daily_schedule.items() if party == "unknown"
    ]
    booked_slots = {
        time: party for time, party in daily_schedule.items() if party != "unknown"
    }

    return {
        "status": "success",
        "message": f"Schedule for {date}.",
        "available_slots": available_slots,
        "booked_slots": booked_slots,
    }


def book_jam_session(
    date: str, start_time: str, end_time: str, reservation_name: str
) -> dict:
    """
    Books a jam session for a given date and time range under a reservation name.

    Args:
        date: The date of the reservation, in YYYY-MM-DD format.
        start_time: The start time of the reservation, in HH:MM format.
        end_time: The end time of the reservation, in HH:MM format.
        reservation_name: The name for the reservation.

    Returns:
        A dictionary confirming the booking or providing an error.
    """
    try:
        start_dt = datetime.strptime(f"{date} {start_time}", "%Y-%m-%d %H:%M")
        end_dt = datetime.strptime(f"{date} {end_time}", "%Y-%m-%d %H:%M")
    except ValueError:
        return {
            "status": "error",
            "message": "Invalid date or time format. Please use YYYY-MM-DD and HH:MM.",
        }

    if start_dt >= end_dt:
        return {"status": "error", "message": "Start time must be before end time."}

    if date not in JAM_SPOT_SCHEDULE:
        return {"status": "error", "message": f"The jam spot is not open on {date}."}

    if not reservation_name:
        return {
            "status": "error",
            "message": "Cannot book a jam spot without a reservation name.",
        }

    required_slots = []
    current_time = start_dt
    while current_time < end_dt:
        required_slots.append(current_time.strftime("%H:%M"))
        current_time += timedelta(hours=1)

    daily_schedule = JAM_SPOT_SCHEDULE.get(date, {})
    for slot in required_slots:
        if daily_schedule.get(slot, "booked") != "unknown":
            party = daily_schedule.get(slot)
            return {
                "status": "error",
                "message": f"The time slot {slot} on {date} is already booked by {party}.",
            }

    for slot in required_slots:
        JAM_SPOT_SCHEDULE[date][slot] = reservation_name

    return {
        "status": "success",
        "message": f"Success! The jam session has been booked for {reservation_name} from {start_time} to {end_time} on {date}.",
    }
