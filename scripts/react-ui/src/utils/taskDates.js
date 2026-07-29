export const taskDayBounds = (dateInput) => {
  const start = new Date(`${dateInput}T00:00:00`);
  const end = new Date(start);
  end.setDate(end.getDate() + 1);
  return { fromTime: start.toISOString(), toTime: end.toISOString() };
};
