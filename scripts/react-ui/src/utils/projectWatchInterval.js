const intervalUnitToMinutes = {
  minutes: 1,
  hours: 60,
  days: 60 * 24,
};

export const toScanIntervalMinutes = (value, unit) => {
  return Number(value) * (intervalUnitToMinutes[unit] || 1);
};

export const fromScanIntervalMinutes = (minutes = 30) => {
  if (minutes % intervalUnitToMinutes.days === 0) {
    return { scan_interval_value: minutes / intervalUnitToMinutes.days, scan_interval_unit: 'days' };
  }
  if (minutes % intervalUnitToMinutes.hours === 0) {
    return { scan_interval_value: minutes / intervalUnitToMinutes.hours, scan_interval_unit: 'hours' };
  }
  return { scan_interval_value: minutes, scan_interval_unit: 'minutes' };
};
