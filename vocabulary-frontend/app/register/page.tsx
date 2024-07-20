// app/register/page.tsx
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import axios from 'axios';
import Header from '../ui/components/Header';

const Register: React.FC = () => {
    const [username, setUsername] = useState('');
    const [error, setError] = useState('');
    const router = useRouter();

    const handleUsernameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setUsername(e.target.value);
    };

    const handleRegister = async (event: React.FormEvent) => {
        event.preventDefault();
        try {
            const response = await axios.post(`${process.env.NEXT_PUBLIC_API_URL}/users`, { user_name: username });
            if (response.status === 201) {
                router.push(`/user/${response.data.user_id}`);
            }
        } catch (error) {
            console.log(error)
            if (axios.isAxiosError(error) && error.response?.status === 409) {
                setError('User with the username already exists.');
            } else {
                setError('An error occurred while creating the user.');
            }
        }
    };

    return (
        <main className="flex min-h-screen flex-col items-center justify-center p-24">
            <Header showLoginButton={true} />
            <h2 className="text-4xl font-bold mb-8">Register</h2>
            <form className="w-full max-w-md" onSubmit={handleRegister}>
                <div className="mb-4">
                    <label className="block text-gray-700 text-sm font-bold mb-2" htmlFor="username">
                        Username
                    </label>
                    <input
                        className="shadow appearance-none border rounded w-full py-2 px-3 text-gray-700 leading-tight focus:outline-none focus:shadow-outline"
                        id="username"
                        type="text"
                        value={username}
                        onChange={handleUsernameChange}
                        placeholder="Enter your username"
                        required
                    />
                </div>
                <div className="flex items-center justify-between">
                    <button
                        className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded focus:outline-none focus:shadow-outline"
                        type="submit"
                    >
                        Register
                    </button>
                </div>
            </form>
            {error && <p className="mt-4 text-red-500">{error}</p>}
        </main>
    );
};

export default Register;
