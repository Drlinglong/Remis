import React from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const COLORS = [
    'var(--chart-series-1)',
    'var(--chart-series-2)',
    'var(--chart-series-3)',
    'var(--chart-series-4)',
    'var(--chart-series-5)',
    'var(--chart-series-6)',
    'var(--chart-series-7)',
];

const ProjectDistributionPieChart = ({ data: dynamicData }) => {
    const { t } = useTranslation();

    const defaultData = [
        { name: 'No Projects', value: 0 },
    ];

    // Helper to translate game names if needed, or format them nicely
    const formatName = (name) => {
        // Try to find a translation key for the game name, otherwise capitalize
        const key = `game_name_${name.toLowerCase()}`;
        const translated = t(key);
        return translated !== key ? translated : name.charAt(0).toUpperCase() + name.slice(1);
    };

    const data = dynamicData && dynamicData.length > 0
        ? dynamicData.map(d => ({ ...d, name: formatName(d.name) }))
        : defaultData;

    const isDefault = !dynamicData || dynamicData.length === 0;

    return (
        <ResponsiveContainer width="100%" height={300}>
            <PieChart>
                <Pie
                    data={data}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                    isAnimationActive={false}
                    stroke="none"
                >
                    {data.map((entry, index) => (
                        <Cell
                            key={`cell-${index}`}
                            fill={isDefault ? 'var(--chart-empty)' : COLORS[index % COLORS.length]}
                            fillOpacity={isDefault ? 0.3 : 1}
                        />
                    ))}
                </Pie>
                <Tooltip
                    contentStyle={{
                        background: 'var(--chart-tooltip-bg)',
                        border: '1px solid var(--chart-tooltip-border)',
                        borderRadius: 'var(--radius-paper)',
                        boxShadow: 'var(--shadow-elevated)',
                        color: 'var(--chart-tooltip-text)',
                    }}
                    itemStyle={{ color: 'var(--chart-tooltip-text)' }}
                    labelStyle={{ color: 'var(--chart-tooltip-text)' }}
                />
                <Legend wrapperStyle={{ paddingTop: '20px' }} />
            </PieChart>
        </ResponsiveContainer>
    );
};

export default ProjectDistributionPieChart;
