import React from 'react';
import { Link } from 'react-router';
import { Card, Text, ThemeIcon, Group, Stack } from '@mantine/core';
import { IconArrowRight } from '@tabler/icons-react';

const ActionCard = ({ icon, title, description, linkTo, color = 'blue', className }) => {
  return (
    <Link to={linkTo} style={{ textDecoration: 'none' }}>
      <Card
        shadow="sm"
        padding="xl"
        radius="md"
        withBorder
        className={className}
        style={{
          transition: 'transform 0.2s ease, box-shadow 0.2s ease',
          cursor: 'pointer'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.transform = 'translateY(-5px)';
          e.currentTarget.style.boxShadow = '0 10px 20px rgba(0,0,0,0.2)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.transform = 'translateY(0)';
          e.currentTarget.style.boxShadow = 'none';
        }}
      >
        <Group align="flex-start" justify="space-between" mb="xs">
          <ThemeIcon size={60} radius="md" variant="light" color={color}>
            {icon}
          </ThemeIcon>
          <ThemeIcon variant="subtle" color="gray">
            <IconArrowRight size={20} />
          </ThemeIcon>
        </Group>

        <Text fw={700} size="xl" mt="md">{title}</Text>
        {description && <Text size="sm" c="dimmed" mt="xs">{description}</Text>}
      </Card>
    </Link>
  );
};

export default ActionCard;
