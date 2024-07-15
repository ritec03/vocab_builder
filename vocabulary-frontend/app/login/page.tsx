// app/login/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import Header from '../ui/components/Header';

const Login: React.FC = () => {
    const [userId, setUserId] = useState('');
    const [error, setError] = useState('');
    const router = useRouter();

    const handleUserIdChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUserId(e.target.value);
    };

    const handleLogin = async (event: React.FormEvent) => {
        event.preventDefault();
        try {
            const response = await axios.get(`${process.env.NEXT_PUBLIC_API_URL}/users/${userId}`);
            if (response.status === 200) {
                router.push(`/user/${userId}`);
            }
        } catch (error) {
            if (axios.isAxiosError(error) && error.response?.status === 404) {
                setError('User not found.');
            } else {
                setError('An error occurred while fetching the user.');
            }
        }
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header showRegisterButton={true} />
            <h2 className="text-4xl font-bold mb-8">Login</h2>
            <form className="w-full max-w-md" onSubmit={handleLogin}>
                <div className="mb-4">
                    <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="userId">
                        User ID
                    </label>
                    <input
                        className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                        id="userId"
                        type="text"
                        value={userId}
                        onChange={handleUserIdChange}
                        placeholder="Enter your user ID"
                        required
                    />
                </div>
                <div className="flex items-center justify-between">
                    <button
                        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                        type="submit"
                    >
                        Sign In
                    </button>
                </div>
            </form>
            {error && <p className="mt-4 text-red-500">{error}</p>}
        </main>
    );
};

export default Login;
