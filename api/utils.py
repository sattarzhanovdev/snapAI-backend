from datetime import date
from .models import GoalType, ActivityLevel

# активность в множители TDEE
ACTIVITY_MULT = {
    ActivityLevel.SEDENTARY: 1.2,
    ActivityLevel.NORMAL: 1.375,
    ActivityLevel.ACTIVE: 1.55,
}

def years_from_birth(dob):
    if not dob:
        return 30  # дефолт
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def mifflin_st_jeor(gender, weight_kg, height_cm, age):
    if not (weight_kg and height_cm and age):
        return None
    s = 5 if gender == "male" else -161
    return int(10 * weight_kg + 6.25 * height_cm - 5 * age + s)


def plan_from_profile(profile):
    age = years_from_birth(profile.date_of_birth)
    bmr = mifflin_st_jeor(profile.gender, profile.weight_kg, profile.height_cm, age)
    if bmr is None:
        return None

    tdee = int(bmr * ACTIVITY_MULT.get(profile.activity, 1.375))

    # смещение по цели
    if profile.goal == GoalType.LOSE:
        calories = tdee - 400
    elif profile.goal == GoalType.GAIN:
        calories = tdee + 300
    else:
        calories = tdee

    # БЖУ: 25/30/45 (настраиваемо)
    protein_g = int((calories * 0.25) / 4)
    fat_g = int((calories * 0.30) / 9)
    carbs_g = int((calories * 0.45) / 4)

    return {
        "calories": max(calories, 1200),  # нижний порог
        "protein_g": protein_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
    }
