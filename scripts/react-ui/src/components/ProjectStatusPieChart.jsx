import React from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Modern Dark Theme Colors mapped by status (Matching KanbanColumn.jsx logic)
const STATUS_COLORS = {
  'todo': '#adb5bd',         // Gray
  'in_progress': '#339af0',  // Blue
  'proofreading': '#d9a300', // Yellow (Darker for visibility)
  'paused': '#fb8c00',       // Orange
  'done': '#40c057',         // Green
};

const ProjectStatusPieChart = ({ data: dynamicData }) => {
  const { t } = useTranslation();

  const statusMap = {
    'todo': t('project_management.kanban.columns.todo'),
    'in_progress': t('project_management.kanban.columns.in_progress'),
    'proofreading': t('project_management.kanban.columns.proofreading'),
    'paused': t('project_management.kanban.columns.paused'),
    'done': t('project_management.kanban.columns.done'),
  };

  const defaultData = [
    { name: 'todo', value: 0 },
    { name: 'in_progress', value: 0 },
    { name: 'proofreading', value: 0 },
    { name: 'paused', value: 0 },
    { name: 'done', value: 0 },
  ];

  const data = dynamicData && dynamicData.length > 0
    ? dynamicData.map(d => ({ ...d, displayName: statusMap[d.name.toLowerCase()] || d.name }))
    : defaultData.map(d => ({ ...d, displayName: statusMap[d.name] }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie
          data={data}
          cx="50%"
          cy="50%"
          innerRadius={60} // Donut chart looks more modern
          outerRadius={100}
          paddingAngle={5}
          dataKey="value"
          nameKey="displayName"
          stroke="none"
        >
          {data.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={STATUS_COLORS[entry.name.toLowerCase()] || '#adb5bd'} />
          ))}
        </Pie>
        <Tooltip
          contentStyle={{ backgroundColor: 'var(--glass-bg)', borderColor: 'var(--glass-border)', color: 'var(--text-main)', backdropFilter: 'blur(10px)' }}
          itemStyle={{ color: 'var(--text-main)' }}
        />
        <Legend wrapperStyle={{ paddingTop: '20px' }} />
      </PieChart>
    </ResponsiveContainer>
  );
};

export default ProjectStatusPieChart;
