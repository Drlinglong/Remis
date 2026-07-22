const GAME_BADGE_COLORS = {
  victoria3: 'blue',
  hoi4: 'olive',
  stellaris: 'grape',
  eu4: 'cyan',
  eu5: 'orange',
  ck3: 'red',
};

export function getGameBadgeColor(gameId) {
  return GAME_BADGE_COLORS[String(gameId || '').toLowerCase()] || 'gray';
}
