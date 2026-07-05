export const getWeekDateRange = (year: number, week: number): string => {
  const jan4 = new Date(year, 0, 4);
  let dayOfWeek = jan4.getDay();
  if (dayOfWeek === 0) dayOfWeek = 7;
  const week1Monday = new Date(year, 0, 4 - (dayOfWeek - 1));
  const targetMonday = new Date(week1Monday.getTime() + (week - 1) * 7 * 24 * 60 * 60 * 1000);

  const targetFriday = new Date(targetMonday.getTime() + 4 * 24 * 60 * 60 * 1000);

  return `${targetMonday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })} - ${targetFriday.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`;
};