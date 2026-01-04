import React from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Distinct colors for games
const COLORS = ['#228be6', '#fab005', '#fa5252', '#7950f2', '#15aabf', '#82c91e', '#be4bdb'];
// Blue, Yellow, Red, Violet, Cyan, Lime, Grape

const ProjectDistributionPieChart = ({ data: dynamicData }) => {
    const { t } = useTranslation();

    const defaultData = [
        { name: 'No Projects', value: 1 },
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
                    stroke="none"
                >
                    {data.map((entry, index) => (
                        <Cell
                            key={`cell-${index}`}
                            fill={isDefault ? '#444' : COLORS[index % COLORS.length]}
                            fillOpacity={isDefault ? 0.3 : 1}
                        />
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

export default ProjectDistributionPieChart;
