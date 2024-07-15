// app/page.tsx
'use client';

import Header from './ui/components/Header';

const Home: React.FC = () => {
    return (
        <main className="flex min-h-screen flex-col items-center justify-between p-24">
            <Header showLoginButton={true} showRegisterButton={true} />
            <div className="flex flex-col items-center justify-center text-center mt-16">
                <h2 className="text-4xl font-bold mb-4">Welcome to the Vocabulary Learning App</h2>
                <p className="text-lg">Enhance your vocabulary with our interactive lessons and quizzes.</p>
            </div>
        </main>
    );
};

export default Home;
