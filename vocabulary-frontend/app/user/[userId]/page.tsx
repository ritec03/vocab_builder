// app/user/[userId]/page.tsx
'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import axios from 'axios';
import Header from '../../ui/components/Header';

interface User {
    id: number;
    name: string;
}

const UserPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const [user, setUser] = useState<User | null>(null);
    const [error, setError] = useState('');

    useEffect(() => {
        if (userId) {
            axios.get(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}`)
                .then(response => {
                    setUser(response.data);
                    setError('');
                })
                .catch(error => {
                    if (axios.isAxiosError(error) && error.response?.status === 404) {
                        setError('User not found.');
                    } else {
                        setError('An error occurred while fetching the user.');
                    }
                    setUser(null);
                });
        }
    }, [userId]);

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header />
            {user ? (
                <div className="text-center">
                    <h1 className="text-4xl font-bold mb-4">User Profile</h1>
                    <p className="text-lg">User ID: {user.id}</p>
                    <p className="text-lg">User Name: {user.name}</p>
                </div>
            ) : (
                <p className="mt-4 text-red-500">{error}</p>
            )}
        </main>
    );
};

export default UserPage;
