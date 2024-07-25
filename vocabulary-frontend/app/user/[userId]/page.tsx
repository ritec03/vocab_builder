// app/user/[userId]/page.tsx
'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useQuery, QueryClient } from '@tanstack/react-query';
import axios from 'axios';
import Header from '../../ui/components/Header';

interface User {
    id: number;
    name: string;
}

const fetchUser = async (userId: string): Promise<User> => {
    const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}`);
    return response.data;
}

const UserPage: React.FC = () => {
    const params = useParams();
    const userId = params.userId as string;
    const router = useRouter();
    const [user, setUser] = useState<User | null>(null);

    const {data: user_data, error, isError, isLoading} = useQuery({
        queryKey: ['user', userId], 
        queryFn: async () => {
            const data = await fetchUser(userId);
            setUser(data);
            return data;
        }
    });

    const handleStartLesson = () => {
        router.push(`/user/${userId}/lesson`);
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header />
            {isLoading ? (
                <p>Loading...</p>
            ) : user ? (
                <div className="text-center">
                    <h1 className="text-4xl font-bold mb-4">User Profile</h1>
                    <p className="text-lg">User ID: {user.id}</p>
                    <p className="text-lg">User Name: {user.name}</p>
                    <button
                        onClick={handleStartLesson}
                        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline mt-4"
                    >
                        Start Lesson
                    </button>
                </div>
            ) : (
                <p className="mt-4 text-red-500">{error?.message}</p>
            )}
        </main>
    );
};

export default UserPage;
