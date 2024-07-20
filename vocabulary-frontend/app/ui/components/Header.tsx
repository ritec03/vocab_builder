'use client';

import Link from 'next/link';

interface HeaderProps {
    showLoginButton?: boolean;
    showRegisterButton?: boolean;
}

const Header: React.FC<HeaderProps> = ({ showLoginButton, showRegisterButton }) => {
    return (
        <header className="w-full flex justify-between items-center py-4 px-8 bg-gray-800 text-white">
            <Link href="/">
                <h1 className="text-2xl font-bold cursor-pointer">Welcome to Vocabulary App</h1>
            </Link>
            <div>
                {showLoginButton && (
                    <Link href="/login" className="mr-4 text-lg">
                        Login
                    </Link>
                )}
                {showRegisterButton && (
                    <Link href="/register" className="text-lg">
                        Register
                    </Link>
                )}
            </div>
        </header>
    );
};

export default Header;
