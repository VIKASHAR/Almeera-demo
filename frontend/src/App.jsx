import React, { useState, useEffect, useRef } from 'react';
import { 
  Send, 
  Store, 
  Globe, 
  User, 
  Tag, 
  Flame, 
  Check, 
  AlertCircle, 
  Plus, 
  Coffee,
  ShoppingCart,
  ArrowLeft,
  X,
  Search,
  ChevronRight,
  ChevronLeft,
  MessageSquare,
  ShieldAlert
} from 'lucide-react';

const BACKEND_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const jsonParseSafe = (str) => {
  try {
    return typeof str === 'string' ? JSON.parse(str) : (str || {});
  } catch (e) {
    return {};
  }
};

const mapCustomerPreferences = (prefJson) => {
  const parsed = jsonParseSafe(prefJson);
  return {
    ...parsed,
    dietary_preference: parsed.diet || parsed.dietary_preference || 'none',
    avoid_list: parsed.allergies || parsed.avoid_list || [],
    favorite_categories: parsed.favorite_categories || []
  };
};

const MOCK_BEVERAGES = [
  {
    sku: "B1",
    name: "Al Meera Fresh Orange Juice 1L",
    category: "Beverages",
    subcategory: "Juice",
    brand: "Al Meera",
    price: 3.49,
    stock_qty: 25,
    attributes_json: JSON.stringify({ organic: true, vegan: true, dairy_free: true, gluten_free: true, fat_content: "non-fat" }),
    promotion: { discount_pct: 0.15, description: "15% Off Fresh Juice Promotion" }
  },
  {
    sku: "B2",
    name: "Al Meera Lemon Mint Juice 1L",
    category: "Beverages",
    subcategory: "Juice",
    brand: "Al Meera",
    price: 2.99,
    stock_qty: 30,
    attributes_json: JSON.stringify({ organic: true, vegan: true, dairy_free: true, gluten_free: true, fat_content: "non-fat" }),
    promotion: null
  },
  {
    sku: "B3",
    name: "Rayyan Mineral Water 6x1.5L",
    category: "Beverages",
    subcategory: "Water",
    brand: "Rayyan",
    price: 1.99,
    stock_qty: 45,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "B4",
    name: "Coca Cola Zero Sugar 6x355ml",
    category: "Beverages",
    subcategory: "Soda",
    brand: "Coca-Cola",
    price: 3.99,
    stock_qty: 20,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "B5",
    name: "Lipton Organic Green Tea 25 Bags",
    category: "Beverages",
    subcategory: "Tea",
    brand: "Lipton",
    price: 4.49,
    stock_qty: 18,
    attributes_json: JSON.stringify({ organic: true, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: { discount_pct: 0.10, description: "Save 10% on Organic Green Tea" }
  }
];

const MOCK_SNACKS = [
  {
    sku: "S1",
    name: "Lay's Classic Salted Potato Chips",
    category: "Snacks",
    subcategory: "Chips",
    brand: "Lay's",
    price: 1.49,
    stock_qty: 40,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "S2",
    name: "Al Meera Mixed Raw Nuts 250g",
    category: "Snacks",
    subcategory: "Nuts",
    brand: "Al Meera",
    price: 5.99,
    stock_qty: 15,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: { discount_pct: 0.20, description: "20% off Premium Mixed Nuts" }
  },
  {
    sku: "S3",
    name: "Nature Valley Organic Oats & Honey Bar",
    category: "Snacks",
    subcategory: "Granola Bars",
    brand: "Nature Valley",
    price: 3.49,
    stock_qty: 25,
    attributes_json: JSON.stringify({ organic: true, vegan: false, dairy_free: false, gluten_free: false }),
    promotion: null
  },
  {
    sku: "S4",
    name: "Lindt Excellence Dark Chocolate 70%",
    category: "Snacks",
    subcategory: "Chocolate",
    brand: "Lindt",
    price: 2.99,
    stock_qty: 35,
    attributes_json: JSON.stringify({ organic: true, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "S5",
    name: "Al Meera Butter Popcorn 100g",
    category: "Snacks",
    subcategory: "Popcorn",
    brand: "Al Meera",
    price: 1.99,
    stock_qty: 28,
    attributes_json: JSON.stringify({ organic: false, vegan: false, dairy_free: false, gluten_free: true }),
    promotion: { discount_pct: 0.15, description: "15% off movie night popcorn!" }
  }
];

const MOCK_BAKERY = [
  {
    sku: "BK1",
    name: "Al Meera Fresh Sliced White Bread 600g",
    category: "Bakery",
    subcategory: "Bread",
    brand: "Al Meera",
    price: 1.25,
    stock_qty: 15,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: false }),
    promotion: null
  },
  {
    sku: "BK2",
    name: "Al Meera Whole Meal Sliced Bread 600g",
    category: "Bakery",
    subcategory: "Bread",
    brand: "Al Meera",
    price: 1.49,
    stock_qty: 12,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: false }),
    promotion: { discount_pct: 0.10, description: "10% off healthy bread" }
  },
  {
    sku: "BK3",
    name: "Al Meera Fresh Butter Croissants 4s",
    category: "Bakery",
    subcategory: "Croissant",
    brand: "Al Meera",
    price: 2.19,
    stock_qty: 8,
    attributes_json: JSON.stringify({ organic: false, vegan: false, dairy_free: false, gluten_free: false }),
    promotion: null
  }
];

const MOCK_HOUSEHOLD = [
  {
    sku: "HH1",
    name: "Al Meera Facial Tissues 5x200 Sheets",
    category: "Household",
    subcategory: "Tissues",
    brand: "Al Meera",
    price: 3.29,
    stock_qty: 50,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: { discount_pct: 0.15, description: "Save on tissues pack" }
  },
  {
    sku: "HH2",
    name: "Al Meera Premium Dishwashing Liquid 1L",
    category: "Household",
    subcategory: "Dishwashing",
    brand: "Al Meera",
    price: 2.49,
    stock_qty: 35,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: null
  },
  {
    sku: "HH3",
    name: "Al Meera Multi-Purpose Glass Cleaner 500ml",
    category: "Household",
    subcategory: "Cleaner",
    brand: "Al Meera",
    price: 1.99,
    stock_qty: 20,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: null
  }
];

const MOCK_BABY = [
  {
    sku: "BB1",
    name: "Al Meera Sensitive Baby Wipes 80 Sheets",
    category: "Baby",
    subcategory: "Wipes",
    brand: "Al Meera",
    price: 1.89,
    stock_qty: 40,
    attributes_json: JSON.stringify({ organic: false, alcohol_free: true }),
    promotion: null
  },
  {
    sku: "BB2",
    name: "Al Meera Baby Powder 200g",
    category: "Baby",
    subcategory: "Powder",
    brand: "Al Meera",
    price: 2.99,
    stock_qty: 25,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: null
  }
];

const MOCK_PET = [
  {
    sku: "PT1",
    name: "Purina Alpo Beef Dry Dog Food 1.5kg",
    category: "Pet",
    subcategory: "Dog Food",
    brand: "Purina",
    price: 6.99,
    stock_qty: 15,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: null
  },
  {
    sku: "PT2",
    name: "Whiskas Ocean Fish Dry Cat Food 1.2kg",
    category: "Pet",
    subcategory: "Cat Food",
    brand: "Whiskas",
    price: 5.99,
    stock_qty: 18,
    attributes_json: JSON.stringify({ organic: false }),
    promotion: { discount_pct: 0.10, description: "10% off Cat Food" }
  }
];

const categoryBanners = {
  'Produce': {
    title: "Fresh Fruits & Vegetables",
    desc: "Handpicked fresh fruits, local organic leafy greens, and quality vegetables delivered daily from local farms.",
    bg: "linear-gradient(135deg, #ecfdf5 0%, #a7f3d0 100%)",
    border: "#6ee7b7",
    color: "#047857"
  },
  'Dairy': {
    title: "Dairy, Cheese & Eggs",
    desc: "Explore fresh low-fat milk, local yogurt, butter, and cheeses tailored to your healthy dietary preferences.",
    bg: "linear-gradient(135deg, #eff6ff 0%, #bfdbfe 100%)",
    border: "#93c5fd",
    color: "#1d4ed8"
  },
  'Pantry/Grains': {
    title: "Pantry & Cooking Staples",
    desc: "Stock up your pantry with standard pastas, extra virgin olive oil, rice, and delicious curry powders.",
    bg: "linear-gradient(135deg, #fffbeb 0%, #fde68a 100%)",
    border: "#fcd34d",
    color: "#b45309"
  },
  'Beverages': {
    title: "Refreshing Juices & Beverages",
    desc: "Quench your thirst with freshly squeezed orange juice, low-sugar sodas, and hydrating spring water packs.",
    bg: "linear-gradient(135deg, #ecfeff 0%, #cffafe 100%)",
    border: "#22d3ee",
    color: "#0891b2"
  },
  'Snacks': {
    title: "Snacks & Sweets",
    desc: "Snack smart with low-calorie popcorn, dark chocolates, and healthy granola bars for all-day energy.",
    bg: "linear-gradient(135deg, #fff5f5 0%, #fed7d7 100%)",
    border: "#feb2b2",
    color: "#c53030"
  },
  'Diet': {
    title: "Healthy & Diet Choices",
    desc: "Carefully curated Keto, Gluten-Free, Organic, and Low-Fat selections tailored specifically for your diet profiles.",
    bg: "linear-gradient(135deg, #f5f3ff 0%, #ddd6fe 100%)",
    border: "#c4b5fd",
    color: "#6d28d9"
  },
  'Al Meera Products': {
    title: "Al Meera Products",
    desc: "Our exclusive private label brand delivering premium quality products at unbeatable prices across Qatar.",
    bg: "linear-gradient(135deg, #f0fdf4 0%, #bbf7d0 100%)",
    border: "#86efac",
    color: "#166534"
  },
  'Bakery': {
    title: "Bakery & Fresh Bread",
    desc: "Oven-fresh breads, sliced loaves, buns, and croissants baked daily to golden perfection.",
    bg: "linear-gradient(135deg, #fffaf0 0%, #fde8bb 100%)",
    border: "#fcd34d",
    color: "#a16207"
  },
  'Household': {
    title: "Household Essentials",
    desc: "High-quality tissue packs, dishwashing detergents, and cleaning products for a sparkling clean home.",
    bg: "linear-gradient(135deg, #f0f9ff 0%, #bae6fd 100%)",
    border: "#7dd3fc",
    color: "#0369a1"
  },
  'Baby': {
    title: "Baby & Personal Care",
    desc: "Gentle baby wipes, baby powders, and daily personal hygiene essentials for you and your family.",
    bg: "linear-gradient(135deg, #fdf2f8 0%, #fbcfe8 100%)",
    border: "#f9a8d4",
    color: "#be185d"
  }
};



const parseInlineMarkdown = (text) => {
  if (!text) return "";
  const parts = text.split(/\*\*([^*]+)\*\*/g);
  return parts.map((part, idx) => {
    if (idx % 2 === 1) {
      return <strong key={idx} className="md-bold">{part}</strong>;
    }
    return part;
  });
};

const renderMarkdown = (text) => {
  if (!text) return null;
  const lines = text.split('\n');
  return lines.map((line, lineIdx) => {
    // 1. Check for Headers
    const headerMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headerMatch) {
      const level = headerMatch[1].length;
      const content = parseInlineMarkdown(headerMatch[2]);
      switch (level) {
        case 1: return <h1 key={lineIdx} className="md-h1">{content}</h1>;
        case 2: return <h2 key={lineIdx} className="md-h2">{content}</h2>;
        case 3: return <h3 key={lineIdx} className="md-h3">{content}</h3>;
        default: return <h4 key={lineIdx} className="md-h4">{content}</h4>;
      }
    }
    
    // 2. Check for List Items
    const listMatch = line.match(/^(\s*)[-\*]\s+(.*)$/);
    if (listMatch) {
      const content = parseInlineMarkdown(listMatch[2]);
      return (
        <div key={lineIdx} className="md-li-container" style={{ paddingLeft: `${listMatch[1].length * 8 + 8}px` }}>
          <span className="md-bullet">&bull;</span>
          <span className="md-li-text">{content}</span>
        </div>
      );
    }
    
    // 3. Spacer
    if (line.trim() === '') {
      return <div key={lineIdx} className="md-spacer" />;
    }
    
    // 4. Paragraph
    return <p key={lineIdx} className="md-p">{parseInlineMarkdown(line)}</p>;
  });
};

const QAR_MULTIPLIER = 3.64;

const formatPrice = (price) => {
  if (price === undefined || price === null) return '';
  return `${(price * QAR_MULTIPLIER).toFixed(2)} QAR`;
};

const SIDEBAR_CATEGORIES = [
  { id: null, name: 'All Products', icon: '🛒' },
  { id: 'Produce', name: 'Fruits & Vegetables', icon: '🥬' },
  { id: 'Dairy', name: 'Dairy, Cheese & Eggs', icon: '🥛' },
  { id: 'Pantry/Grains', name: 'Pantry & Cooking Staples', icon: '🌾' },
  { id: 'Beverages', name: 'Beverages', icon: '🥤' },
  { id: 'Snacks', name: 'Snacks & Sweets', icon: '🍿' },
  { id: 'Diet', name: 'Healthy & Diet Choices', icon: '🥗' },
  { id: 'Al Meera Products', name: 'Al Meera Products', icon: '🏷️' },
  { id: 'Bakery', name: 'Bakery & Bread', icon: '🍞' },
  { id: 'Household', name: 'Household Essentials', icon: '🧻' },
  { id: 'Baby', name: 'Baby & Personal Care', icon: '🍼' },
  { id: 'Pet', name: 'Pet Food & Care', icon: '🐶' }
];

const AlMeeraLogo = () => (
  <img 
    src="/almeera-logo-b.svg" 
    alt="Al Meera Logo" 
    style={{ height: '38px', display: 'block', cursor: 'pointer' }} 
  />
);

const MOCK_QATARI_PRODUCTS = [
  {
    sku: "QP1",
    name: "Baladna Fresh Milk Full Cream 2L",
    category: "Dairy",
    subcategory: "Milk",
    brand: "Baladna",
    price: 3.85,
    stock_qty: 30,
    attributes_json: JSON.stringify({ organic: false, vegan: false, dairy_free: false, gluten_free: true }),
    promotion: null
  },
  {
    sku: "QP2",
    name: "Baladna Fresh Premium Laban 2L",
    category: "Dairy",
    subcategory: "Laban",
    brand: "Baladna",
    price: 3.50,
    stock_qty: 25,
    attributes_json: JSON.stringify({ organic: false, vegan: false, dairy_free: false, gluten_free: true }),
    promotion: { discount_pct: 0.10, description: "10% off Baladna Laban" }
  },
  {
    sku: "QP3",
    name: "Rayyan Pure Natural Water 6x1.5L",
    category: "Beverages",
    subcategory: "Water",
    brand: "Rayyan",
    price: 1.99,
    stock_qty: 50,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "QP4",
    name: "Dandy Fresh Orange Juice 1.5L",
    category: "Beverages",
    subcategory: "Juice",
    brand: "Dandy",
    price: 2.75,
    stock_qty: 20,
    attributes_json: JSON.stringify({ organic: false, vegan: true, dairy_free: true, gluten_free: true }),
    promotion: null
  },
  {
    sku: "QP5",
    name: "Mazzraty Fresh Chicken Breast 450g",
    category: "Fresh Food",
    subcategory: "Poultry",
    brand: "Mazzraty",
    price: 5.49,
    stock_qty: 15,
    attributes_json: JSON.stringify({ organic: true, vegan: false, dairy_free: true, gluten_free: true }),
    promotion: null
  }
];

function App() {
  // Storefront navigation state
  const [view, setView] = useState('home'); // 'home' | 'category' | 'product'
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [selectedSku, setSelectedSku] = useState(null);
  const [detailedProduct, setDetailedProduct] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchInput, setSearchInput] = useState('');

  // Cart State
  const [cart, setCart] = useState([]);
  const [isCartOpen, setIsCartOpen] = useState(false);

  // Chat Widget State
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  // Catalog & Customer States
  const [categories, setCategories] = useState([]);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState('c1');
  const [activeCustomer, setActiveCustomer] = useState(null);
  const [channel, setChannel] = useState('online'); // 'online' | 'in_store'

  // Carousel State & Effect
  const [currentSlide, setCurrentSlide] = useState(0);
  const [isHovered, setIsHovered] = useState(false);

  // Al Meera Header Widgets State
  const [isProfileDropdownOpen, setIsProfileDropdownOpen] = useState(false);
  const [deliveryMode, setDeliveryMode] = useState('scheduled'); // 'instant' | 'scheduled'

  const carouselSlides = [
    {
      id: 1,
      title: "Freshness & Value Delivered Daily",
      desc: "Welcome to the official Al Meera online store. Browse fresh produce, dairy, bakery, weekly discount flyer items, and premium private labels.",
      btnText: "Shop Fresh Produce",
      action: () => setSelectedCategory('Produce'),
      bgGradient: "linear-gradient(135deg, #eef5f0 0%, #dcfce7 100%)",
      borderColor: "#bbf7d0",
      titleColor: "var(--primary)",
      illustration: () => (
        <svg width="200" height="160" viewBox="0 0 200 160" fill="none" className="carousel-illustration">
          <path d="M100 130 C70 130 50 100 50 70 C50 40 70 20 100 20 C130 20 150 40 150 70 C150 100 130 130 100 130 Z" fill="#1b7a3e" fillOpacity="0.1" />
          <path d="M100 120 C80 120 70 100 70 80 C70 60 80 40 100 40 C120 40 130 60 130 80 C130 100 120 120 100 120 Z" fill="#22c55e" fillOpacity="0.2" />
          <path d="M100 140 C100 100 80 70 100 30 C120 70 100 100 100 140 Z" fill="#1b7a3e" />
          <path d="M100 30 C80 50 60 80 80 100 C90 90 95 70 100 30 Z" fill="#22c55e" />
          <path d="M100 30 C120 50 140 80 120 100 C110 90 105 70 100 30 Z" fill="#4ade80" />
          <path d="M60 140 H140" stroke="#b89309" strokeWidth="4" strokeLinecap="round" />
        </svg>
      )
    },
    {
      id: 2,
      title: "Weekly Super Deals & Flyers",
      desc: "Save big on your weekly grocery shopping! Enjoy exclusive discounts up to 50% on selected essentials, pantry goods, and pantry favorites.",
      btnText: "Browse Super Deals",
      action: () => {
        setSearchQuery('');
        setSelectedCategory(null);
        setTimeout(() => {
          document.getElementById('weekly-deals-section')?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      },
      bgGradient: "linear-gradient(135deg, #fee2e2 0%, #fecaca 100%)",
      borderColor: "#fca5a5",
      titleColor: "var(--secondary)",
      illustration: () => (
        <svg width="200" height="160" viewBox="0 0 200 160" fill="none" className="carousel-illustration">
          <circle cx="100" cy="80" r="60" fill="#cf2a27" fillOpacity="0.1" />
          <path d="M100 25 L112 45 L135 40 L135 63 L155 72 L143 92 L150 115 L128 118 L118 138 L98 130 L80 142 L72 120 L50 115 L58 93 L45 74 L65 67 L65 44 L88 47 Z" fill="#cf2a27" />
          <circle cx="100" cy="82" r="32" fill="#b89309" />
          <circle cx="100" cy="82" r="28" fill="#fcd34d" />
          <text x="100" y="90" fontFamily="'Outfit', sans-serif" fontWeight="900" fontSize="24" fill="#cf2a27" textAnchor="middle">50%</text>
          <text x="100" y="104" fontFamily="'Outfit', sans-serif" fontWeight="700" fontSize="10" fill="#cf2a27" textAnchor="middle">OFF</text>
        </svg>
      )
    },
    {
      id: 3,
      title: "Join Al Meera WAFA Rewards",
      desc: "Qatar's most rewarding loyalty program! Scan your digital barcode at checkout, earn points on every purchase, and redeem them for shopping vouchers.",
      btnText: "View Rewards Program",
      action: () => {
        setTimeout(() => {
          document.getElementById('wafa-rewards-section')?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      },
      bgGradient: "linear-gradient(135deg, #fef3c7 0%, #fde68a 100%)",
      borderColor: "#fcd34d",
      titleColor: "var(--accent)",
      illustration: () => (
        <svg width="220" height="160" viewBox="0 0 220 160" fill="none" className="carousel-illustration">
          <rect x="25" y="35" width="170" height="100" rx="12" fill="url(#wafaCardGrad)" filter="drop-shadow(0 10px 15px rgba(27, 122, 62, 0.3))" />
          <circle cx="45" cy="55" r="10" fill="#b89309" fillOpacity="0.8" />
          <circle cx="45" cy="55" r="6" fill="#fcd34d" />
          <text x="65" y="60" fontFamily="'Outfit', sans-serif" fontWeight="800" fontSize="13" fill="#ffffff">WAFA</text>
          <text x="175" y="60" fontFamily="'Outfit', sans-serif" fontWeight="600" fontSize="8" fill="#fcd34d" textAnchor="end">REWARDS</text>
          <rect x="45" y="95" width="80" height="20" fill="white" rx="2" />
          <path d="M50 98 V112 M53 98 V112 M58 98 V112 M63 98 V112 M65 98 V112 M70 98 V112 M76 98 V112 M80 98 V112 M85 98 V112 M90 98 V112 M96 98 V112 M100 98 V112 M105 98 V112 M110 98 V112 M115 98 V112 M120 98 V112" stroke="black" strokeWidth="1.5" />
          <text x="45" y="85" fontFamily="monospace" fontSize="8" fill="#ffffff" opacity="0.8">974 012 345 678</text>
          <defs>
            <linearGradient id="wafaCardGrad" x1="25" y1="35" x2="195" y2="135" gradientUnits="userSpaceOnUse">
              <stop stopColor="#1b7a3e" />
              <stop offset="0.7" stopColor="#0c3b1e" />
              <stop offset="1" stopColor="#b89309" />
            </linearGradient>
          </defs>
        </svg>
      )
    },
    {
      id: 4,
      title: "Purely Healthy & Special Diets",
      desc: "Fuel your lifestyle with our specialty healthy selection. Browse Keto, Vegan, Gluten-Free, and Organic products picked for your nutritional profile.",
      btnText: "Shop Healthy Diets",
      action: () => setSelectedCategory('Diet'),
      bgGradient: "linear-gradient(135deg, #faf5ff 0%, #f3e8ff 100%)",
      borderColor: "#e9d5ff",
      titleColor: "var(--rec-violet)",
      illustration: () => (
        <svg width="200" height="160" viewBox="0 0 200 160" fill="none" className="carousel-illustration">
          <circle cx="100" cy="80" r="55" fill="#7c3aed" fillOpacity="0.1" />
          <path d="M50 80 C50 115 150 115 150 80 H50 Z" fill="#7c3aed" />
          <circle cx="80" cy="72" r="16" fill="#10b981" />
          <circle cx="80" cy="72" r="8" fill="#047857" />
          <circle cx="80" cy="72" r="4" fill="#064e3b" />
          <path d="M105 60 C95 65 95 80 110 75 C120 70 115 60 105 60 Z" fill="#34d399" />
          <path d="M125 65 C115 70 120 85 130 75 C135 70 135 60 125 65 Z" fill="#059669" />
          <path d="M100 95 C100 95 97 91 94 91 C91 91 89 93 89 96 C89 100 100 105 100 105 C100 105 111 100 111 96 C111 93 109 91 106 91 C103 91 100 95 100 95 Z" fill="#ffffff" />
        </svg>
      )
    }
  ];

  useEffect(() => {
    if (isHovered) return;
    const interval = setInterval(() => {
      setCurrentSlide(prev => (prev + 1) % carouselSlides.length);
    }, 5000);
    return () => clearInterval(interval);
  }, [isHovered, carouselSlides.length]);

  // Fetch customers on load
  useEffect(() => {
    fetch(`${BACKEND_URL}/customers`)
      .then(res => res.json())
      .then(data => {
        setCustomers(data);
        if (data.length > 0) {
          const defaultCust = data.find(c => c.customer_id === 'c1') || data[0];
          setSelectedCustomerId(defaultCust.customer_id);
          setActiveCustomer({
            ...defaultCust,
            preferences: mapCustomerPreferences(defaultCust.preferences_json)
          });
        }
      })
      .catch(err => console.error("Error fetching customers:", err));
  }, []);

  // Update active customer details when selection changes
  useEffect(() => {
    if (customers.length > 0) {
      const cust = customers.find(c => c.customer_id === selectedCustomerId);
      if (cust) {
        setActiveCustomer({
          ...cust,
          preferences: mapCustomerPreferences(cust.preferences_json)
        });
      }
    }
  }, [selectedCustomerId, customers]);

  // Fetch categories on load
  useEffect(() => {
    fetch(`${BACKEND_URL}/api/categories`)
      .then(res => res.json())
      .then(data => {
        const uniqueCategories = Array.from(new Set([...data, 'Beverages', 'Snacks', 'Diet', 'Al Meera Products', 'Bakery', 'Household', 'Baby', 'Pet']));
        setCategories(uniqueCategories);
      })
      .catch(err => {
        console.error("Error fetching categories:", err);
        setCategories(['Produce', 'Dairy', 'Pantry/Grains', 'Beverages', 'Snacks', 'Diet', 'Al Meera Products', 'Bakery', 'Household', 'Baby', 'Pet']);
      });
  }, []);

  // Fetch products whenever channel, selectedCategory, or searchQuery changes
  useEffect(() => {
    const isDbCategory = selectedCategory && !['Beverages', 'Snacks', 'Diet', 'Al Meera Products', 'Bakery', 'Household', 'Baby', 'Pet', 'Fresh Food', 'Qatari Products', 'Categories'].includes(selectedCategory);
    let url = `${BACKEND_URL}/api/products?channel=${channel}`;
    if (isDbCategory) {
      url += `&category=${encodeURIComponent(selectedCategory)}`;
    }
    if (searchQuery) {
      url += `&search=${encodeURIComponent(searchQuery)}`;
    }
    
    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (selectedCategory === 'Beverages') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_BEVERAGES.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_BEVERAGES);
          }
        } else if (selectedCategory === 'Snacks') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_SNACKS.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_SNACKS);
          }
        } else if (selectedCategory === 'Bakery') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_BAKERY.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_BAKERY);
          }
        } else if (selectedCategory === 'Household') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_HOUSEHOLD.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_HOUSEHOLD);
          }
        } else if (selectedCategory === 'Baby') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_BABY.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_BABY);
          }
        } else if (selectedCategory === 'Pet') {
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            const filtered = MOCK_PET.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
            setProducts(filtered);
          } else {
            setProducts(MOCK_PET);
          }
        } else if (selectedCategory === 'Diet') {
          const healthyDb = data.filter(p => {
            const attrs = jsonParseSafe(p.attributes_json);
            return attrs.organic || attrs.vegan || attrs.gluten_free || attrs.fat_content === 'low-fat' || attrs.fat_content === 'non-fat';
          });
          const healthyMock = [...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET].filter(p => {
            const attrs = jsonParseSafe(p.attributes_json);
            return attrs.organic || attrs.vegan || attrs.gluten_free || attrs.fat_content === 'low-fat' || attrs.fat_content === 'non-fat';
          });
          let combined = [...healthyDb, ...healthyMock];
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            combined = combined.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
          }
          setProducts(combined);
        } else if (selectedCategory === 'Al Meera Products') {
          const alMeeraDb = data.filter(p => p.brand === 'Al Meera' || p.name.toLowerCase().includes('al meera'));
          const alMeeraMock = [...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET].filter(p => p.brand === 'Al Meera' || p.name.toLowerCase().includes('al meera'));
          let combined = [...alMeeraDb, ...alMeeraMock];
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            combined = combined.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
          }
          setProducts(combined);
        } else if (selectedCategory === 'Fresh Food') {
          const freshDb = data.filter(p => p.category === 'Produce' || p.category === 'Dairy');
          let combined = [...freshDb];
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            combined = combined.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
          }
          setProducts(combined);
        } else if (selectedCategory === 'Qatari Products') {
          const qatariDb = data.filter(p => p.brand === 'Rayyan' || p.brand === 'Baladna' || p.brand === 'Dandy' || p.name.toLowerCase().includes('qatar') || p.brand.toLowerCase().includes('qatar'));
          const qatariMock = [...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET, ...MOCK_QATARI_PRODUCTS].filter(p => p.brand === 'Rayyan' || p.brand === 'Baladna' || p.brand === 'Dandy' || p.name.toLowerCase().includes('qatar'));
          let combined = [...qatariDb, ...qatariMock];
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            combined = combined.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
          }
          setProducts(combined);
        } else if (selectedCategory === 'Categories') {
          let combined = [...data, ...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET, ...MOCK_QATARI_PRODUCTS];
          if (searchQuery) {
            const query = searchQuery.toLowerCase();
            combined = combined.filter(p => 
              p.name.toLowerCase().includes(query) || 
              p.subcategory.toLowerCase().includes(query) || 
              p.brand.toLowerCase().includes(query)
            );
          }
          setProducts(combined);
        } else {
          if (!selectedCategory) {
            let combined = [...data, ...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET];
            if (searchQuery) {
              const query = searchQuery.toLowerCase();
              combined = combined.filter(p => 
                p.name.toLowerCase().includes(query) || 
                p.subcategory.toLowerCase().includes(query) || 
                p.brand.toLowerCase().includes(query)
              );
            }
            setProducts(combined);
          } else {
            setProducts(data);
          }
        }
      })
      .catch(err => console.error("Error fetching products:", err));
  }, [channel, selectedCategory, searchQuery]);

  // Fetch detailed product info when selectedSku changes
  useEffect(() => {
    if (selectedSku) {
      const mockProd = [...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET, ...MOCK_QATARI_PRODUCTS].find(p => p.sku === selectedSku);
      if (mockProd) {
        const mockAlts = [...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET, ...MOCK_QATARI_PRODUCTS]
          .filter(p => p.category === mockProd.category && p.sku !== mockProd.sku)
          .slice(0, 4);
        setDetailedProduct({
          ...mockProd,
          stock: { online: mockProd.stock_qty, in_store: mockProd.stock_qty },
          alternatives: mockAlts
        });
      } else {
        fetch(`${BACKEND_URL}/api/products/${selectedSku}?channel=${channel}`)
          .then(res => res.json())
          .then(data => setDetailedProduct(data))
          .catch(err => console.error("Error fetching detailed product:", err));
      }
    } else {
      setDetailedProduct(null);
    }
  }, [selectedSku, channel]);

  // Scroll to bottom of chat
  useEffect(() => {
    if (isChatOpen) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading, isChatOpen]);

  // Resolve product details from list of SKUs (for Chatbot Widget)
  const fetchProductDetailsForChat = async (skus) => {
    if (!skus || skus.length === 0) return [];
    try {
      const res = await fetch(`${BACKEND_URL}/products/details`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ skus })
      });
      return await res.json();
    } catch (err) {
      console.error("Error fetching product details for chat:", err);
      return [];
    }
  };

  // Send message inside Chat Widget
  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!query.trim() || loading) return;

    const userMessage = {
      sender: 'user',
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    setMessages(prev => [...prev, userMessage]);
    setQuery('');
    setLoading(true);

    try {
      const res = await fetch(`${BACKEND_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: selectedCustomerId,
          channel: channel,
          raw_text: userMessage.text,
          session_id: "demo_session"
        })
      });
      const chatResponse = await res.json();

      // Extract all skus in response to fetch details
      const structured = chatResponse.structured || {};
      const primarySkus = structured.primary_skus || [];
      const recommendedSkus = structured.recommended_skus || [];
      const affinitySkus = structured.affinity_skus || [];
      
      const allSkus = [...new Set([...primarySkus, ...recommendedSkus, ...affinitySkus])];
      const productDetails = await fetchProductDetailsForChat(allSkus);
      
      const productsMap = {};
      productDetails.forEach(p => {
        productsMap[p.sku] = p;
      });

      const convertedText = chatResponse.text.replace(/\$(\d+(?:\.\d+)?)/g, (match, p1) => {
        return `${(parseFloat(p1) * QAR_MULTIPLIER).toFixed(2)} QAR`;
      });

      const botMessage = {
        sender: 'bot',
        text: convertedText,
        structured: structured,
        products: productsMap,
        debug_trace: chatResponse.debug_trace,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };

      setMessages(prev => [...prev, botMessage]);
    } catch (err) {
      console.error("Error sending message:", err);
      setMessages(prev => [...prev, {
        sender: 'bot',
        text: "Sorry, I had trouble communicating with the chatbot backend. Make sure the FastAPI server is running on port 8000.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        error: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  // Cart operations
  const handleAddToCart = (product, e) => {
    if (e) e.stopPropagation();
    
    // Check stock first
    const isOutOfStock = product.stock_qty === 0;
    if (isOutOfStock) return;

    setCart(prev => {
      const existing = prev.find(item => item.product.sku === product.sku);
      if (existing) {
        return prev.map(item => 
          item.product.sku === product.sku 
            ? { ...item, qty: item.qty + 1 }
            : item
        );
      }
      return [...prev, { product, qty: 1 }];
    });
  };

  const handleRemoveFromCart = (sku) => {
    setCart(prev => prev.filter(item => item.product.sku !== sku));
  };

  const handleUpdateCartQty = (sku, delta) => {
    setCart(prev => prev.map(item => {
      if (item.product.sku === sku) {
        const newQty = item.qty + delta;
        return newQty > 0 ? { ...item, qty: newQty } : item;
      }
      return item;
    }).filter(item => item.qty > 0));
  };

  const handleAddRecipeIngredients = (ingredients, e) => {
    if (e) e.stopPropagation();
    const allAvailable = [...products, ...MOCK_BEVERAGES, ...MOCK_SNACKS, ...MOCK_BAKERY, ...MOCK_HOUSEHOLD, ...MOCK_BABY, ...MOCK_PET, ...MOCK_QATARI_PRODUCTS];
    const itemsToAdd = [];

    ingredients.forEach(sku => {
      // Look up inside all available products
      const match = allAvailable.find(p => p.sku === sku);
      if (match && match.stock_qty !== 0) {
        itemsToAdd.push(match);
      }
    });

    if (itemsToAdd.length === 0) {
      alert("All ingredients for this recipe are currently out of stock!");
      return;
    }

    setCart(prev => {
      let updated = [...prev];
      itemsToAdd.forEach(p => {
        const existingIdx = updated.findIndex(item => item.product.sku === p.sku);
        if (existingIdx !== -1) {
          updated[existingIdx] = {
            ...updated[existingIdx],
            qty: updated[existingIdx].qty + 1
          };
        } else {
          updated.push({ product: p, qty: 1 });
        }
      });
      return updated;
    });

    alert(`Successfully added ${itemsToAdd.length} fresh ingredients to your cart!`);
  };


  // Allergy / Diet check
  const getProductWarnings = (product) => {
    if (!product || !activeCustomer || !activeCustomer.preferences) return [];
    const warnings = [];
    const prefs = activeCustomer.preferences;
    const diet = prefs.dietary_preference || 'none';
    const allergies = prefs.avoid_list || [];
    
    const attrs = jsonParseSafe(product.attributes_json);

    // Diet Checks
    if (diet === 'low-fat') {
      if (product.category === 'Dairy' && attrs.fat_content !== 'low-fat' && attrs.fat_content !== 'non-fat') {
        warnings.push(`Dietary Violation: Sarah has a Low-Fat diet preference. This dairy product contains standard fat.`);
      }
    } else if (diet === 'vegan') {
      if (attrs.vegan === false) {
        warnings.push(`Dietary Violation: Customer is vegan. This product is marked as non-vegan.`);
      }
    } else if (diet === 'gluten-free') {
      if (attrs.gluten_free === false) {
        warnings.push(`Dietary Violation: Customer is gluten-free. This product contains gluten.`);
      }
    }

    // Allergy Checks
    for (const allergy of allergies) {
      if (allergy === 'dairy') {
        if (attrs.dairy_free === false || product.category === 'Dairy') {
          warnings.push(`⚠️ Allergen Warning: Contains Dairy (violates your Dairy allergy preference).`);
        }
      }
      if (allergy === 'nuts') {
        if (product.name.toLowerCase().includes('almond') || product.name.toLowerCase().includes('peanut') || product.name.toLowerCase().includes('nut')) {
          warnings.push(`⚠️ Allergen Warning: Contains Nuts/Almonds (violates your Nuts allergy preference).`);
        }
      }
    }

    return warnings;
  };

  const cartCount = cart.reduce((sum, item) => sum + item.qty, 0);
  const cartSubtotal = cart.reduce((sum, item) => {
    const discountPct = item.product.promotion?.discount_pct || 0;
    const finalPrice = item.product.price * (1 - discountPct);
    return sum + finalPrice * item.qty;
  }, 0);

  // Search Submit
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    setSearchQuery(searchInput);
    setView('home');
  };

  return (
    <div className="glass-container" style={{ height: '100vh', width: '100vw', maxWidth: 'none', borderRadius: '0', border: 'none', boxShadow: 'none' }}>
      
      {/* 1. STOREFRONT HEADER */}
      <header className="top-header">
        <div className="header-logo-container" onClick={() => { setView('home'); setSelectedCategory(null); setSelectedSku(null); }}>
          <AlMeeraLogo />
        </div>

        {/* Location Selector */}
        <div className="header-location-pill" onClick={() => alert("Deliver to Doha, Qatar selected.")}>
          <Store size={18} style={{ color: '#6b7280' }} />
          <div className="location-text">
            <span className="location-label">Delivering to</span>
            <span className="location-value">Doha, Qatar</span>
          </div>
          <ChevronRight size={12} style={{ color: '#9ca3af', transform: 'rotate(90deg)' }} />
        </div>

        {/* Center Search Bar */}
        <form onSubmit={handleSearchSubmit} className="header-search-container">
          <Search size={16} className="header-search-icon" />
          <input 
            type="text" 
            placeholder="Search for Fresh Food" 
            className="header-search-input"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
          {searchInput && (
            <X size={16} style={{ position: 'absolute', right: '12px', cursor: 'pointer', color: '#9ca3af' }} onClick={() => { setSearchInput(''); setSearchQuery(''); }} />
          )}
        </form>

        {/* Delivery Modes */}
        <div className="header-delivery-modes">
          <div 
            className={`delivery-mode-pill instant ${deliveryMode === 'instant' ? 'active' : ''}`}
            onClick={() => { setDeliveryMode('instant'); alert("Switched to Instant Delivery (In 40 Mins)"); }}
          >
            <Globe size={16} style={{ color: '#1b7a3e' }} />
            <div className="delivery-text">
              <span className="delivery-title">Instant Delivery</span>
              <span className="delivery-time">In 40 Mins</span>
            </div>
          </div>

          <div 
            className={`delivery-mode-pill scheduled ${deliveryMode === 'scheduled' ? 'active' : ''}`}
            onClick={() => { setDeliveryMode('scheduled'); alert("Switched to Scheduled Delivery (Today, 4:00pm - 6:00pm)"); }}
          >
            <Store size={16} style={{ color: '#fcd34d' }} />
            <div className="delivery-text">
              <span className="delivery-title">Scheduled Delivery</span>
              <span className="delivery-time">Today, 4:00pm - 6:00pm</span>
            </div>
          </div>
        </div>

        {/* Language Selector */}
        <div className="header-lang-selector" onClick={() => alert("Language switcher: Arabic / English")}>
          <span>EN</span>
          <ChevronRight size={12} style={{ color: '#4b5563', transform: 'rotate(90deg)' }} />
        </div>

        {/* Login & Register (Profile Switcher Dropdown) */}
        <div 
          className="header-login-register" 
          onClick={() => setIsProfileDropdownOpen(!isProfileDropdownOpen)}
        >
          <User size={18} style={{ color: '#6b7280' }} />
          <span>{activeCustomer ? activeCustomer.name.split(' ')[0] : 'Login & Register'}</span>
          <ChevronRight size={12} style={{ color: '#4b5563', transform: 'rotate(90deg)' }} />

          {isProfileDropdownOpen && (
            <div className="profile-switcher-dropdown" onClick={e => e.stopPropagation()}>
              <div className="dropdown-header">Switch Demo Profile</div>
              {customers.map(c => {
                const prefs = mapCustomerPreferences(c.preferences_json);
                return (
                  <button 
                    key={c.customer_id}
                    className={`dropdown-item ${selectedCustomerId === c.customer_id ? 'active' : ''}`}
                    onClick={() => {
                      setSelectedCustomerId(c.customer_id);
                      setIsProfileDropdownOpen(false);
                    }}
                  >
                    <span className="dropdown-item-name">{c.name}</span>
                    <span className="dropdown-item-desc">
                      Diet: {prefs.dietary_preference} | Avoid: {prefs.avoid_list.join(', ') || 'None'}
                    </span>
                  </button>
                );
              })}
              
              <div className="dropdown-divider" />
              
              <div className="dropdown-header">Shopping Channel</div>
              <div style={{ padding: '4px 12px', display: 'flex', gap: '8px' }}>
                <button 
                  className={`hero-banner-btn ${channel === 'online' ? 'active' : ''}`}
                  style={{ fontSize: '10px', padding: '4px 8px', flex: 1, background: channel === 'online' ? 'var(--primary)' : '#e5e7eb', color: channel === 'online' ? 'white' : '#4b5563' }}
                  onClick={() => { setChannel('online'); setIsProfileDropdownOpen(false); }}
                >
                  Online
                </button>
                <button 
                  className={`hero-banner-btn ${channel === 'in_store' ? 'active' : ''}`}
                  style={{ fontSize: '10px', padding: '4px 8px', flex: 1, background: channel === 'in_store' ? 'var(--primary)' : '#e5e7eb', color: channel === 'in_store' ? 'white' : '#4b5563' }}
                  onClick={() => { setChannel('in_store'); setIsProfileDropdownOpen(false); }}
                >
                  In-Store
                </button>
              </div>
            </div>
          )}
        </div>
      </header>

      {/* 3. MAIN BODY CONTAINER */}
      <div className="main-body-container" style={{ flex: '1', display: 'flex', overflow: 'hidden' }}>
        
        {/* SIDEBAR */}
        <aside className="sidebar">
          
          {/* Cart sidebar button */}
          <button 
            className={`sidebar-btn ${isCartOpen ? 'active' : ''}`}
            onClick={() => setIsCartOpen(true)}
          >
            <div className="sidebar-icon-container">
              <ShoppingCart size={18} />
              {cartCount > 0 && <span className="sidebar-badge">{cartCount}</span>}
            </div>
            <span className="sidebar-text">Cart</span>
          </button>

          {/* Categories sidebar button */}
          <button 
            className={`sidebar-btn ${selectedCategory === 'Categories' ? 'active' : ''}`}
            onClick={() => {
              setSelectedCategory('Categories');
              setView('home');
              setSelectedSku(null);
            }}
          >
            <div className="sidebar-icon-container">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>
            </div>
            <span className="sidebar-text">Categories</span>
          </button>

          {/* Fresh Food sidebar button */}
          <button 
            className={`sidebar-btn ${selectedCategory === 'Fresh Food' ? 'active' : ''}`}
            onClick={() => {
              setSelectedCategory('Fresh Food');
              setView('home');
              setSelectedSku(null);
            }}
          >
            <div className="sidebar-icon-container">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 2c1.35 0 2.7.2 4 .6C17 4.2 18 6 18 8c0 4.4-4 8-8 12.4M12 2c-1.35 0-2.7.2-4 .6C7 4.2 6 6 6 8c0 4.4 4 8 8 12.4" /><path d="M12 2v18" /></svg>
            </div>
            <span className="sidebar-text">Fresh Food</span>
          </button>

          {/* Qatari Products sidebar button */}
          <button 
            className={`sidebar-btn ${selectedCategory === 'Qatari Products' ? 'active' : ''}`}
            onClick={() => {
              setSelectedCategory('Qatari Products');
              setView('home');
              setSelectedSku(null);
            }}
          >
            <div className="sidebar-icon-container">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M4 4h16v16H4z" fill="#8A1538" rx="4"/><path d="M4 4 L9 8 L4 12 L9 16 L4 20 L4 4" fill="#ffffff"/></svg>
            </div>
            <span className="sidebar-text">Qatari Products</span>
          </button>

          {/* Almeera Products sidebar button */}
          <button 
            className={`sidebar-btn ${selectedCategory === 'Al Meera Products' ? 'active' : ''}`}
            onClick={() => {
              setSelectedCategory('Al Meera Products');
              setView('home');
              setSelectedSku(null);
            }}
          >
            <div className="sidebar-icon-container">
              <svg width="22" height="22" viewBox="0 0 46 44" fill="none">
                <path d="M 5 22 C 3 11 11 3 23 3 C 35 3 43 11 43 22 C 43 33 35 41 23 41 C 11 41 7 33 5 22 Z" fill="#acd600" />
                <path d="M 14 34 C 15 26 21 18 31 10" stroke="#005A36" strokeWidth="2.5" strokeLinecap="round" fill="none" />
                <path d="M 28 12 C 24 13 20 15 17 19" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 24 16 C 20 18 17 21 14 25" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 20 21 C 17 23 14 26 12 31" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 17 26 C 14 28 12 31 10 35" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 28 12 C 29 15 29 19 28 22" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 24 16 C 26 19 26 23 25 26" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 20 21 C 22 24 22 27 21 31" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
                <path d="M 17 26 C 19 29 19 32 18 35" stroke="#005A36" strokeWidth="2.2" strokeLinecap="round" fill="none" />
              </svg>
            </div>
            <span className="sidebar-text">Almeera Products</span>
          </button>

        </aside>

        {/* CONTENT AREA */}
        <div style={{ flex: '1', overflowY: 'auto', padding: '24px 0', display: 'flex', flexDirection: 'column' }}>
          <div className="storefront-container" style={{ flex: '1 0 auto' }}>
          
          {/* A. HOMEPAGE VIEW */}
          {view === 'home' && (
            <>
              {/* Hero Banner / Sliding Carousel */}
              {!selectedCategory && !searchQuery ? (
                <div 
                  className="carousel-container"
                  onMouseEnter={() => setIsHovered(true)}
                  onMouseLeave={() => setIsHovered(false)}
                >
                  <button 
                    className="carousel-arrow left" 
                    onClick={() => setCurrentSlide(prev => (prev === 0 ? carouselSlides.length - 1 : prev - 1))}
                  >
                    <ChevronLeft size={18} />
                  </button>
                  
                  <div className="carousel-slides-wrapper" style={{ transform: `translateX(-${currentSlide * 100}%)` }}>
                    {carouselSlides.map((slide, idx) => (
                      <div 
                        key={slide.id} 
                        className="carousel-slide" 
                        style={{ background: slide.bgGradient, border: `1px solid ${slide.borderColor}` }}
                      >
                        <div className="carousel-slide-split">
                          <div className="carousel-slide-left">
                            <h1 style={{ color: slide.titleColor }}>{slide.title}</h1>
                            <p>{slide.desc}</p>
                            <button className="hero-banner-btn" onClick={slide.action} style={{ background: slide.titleColor }}>
                              {slide.btnText}
                            </button>
                          </div>
                          <div className="carousel-slide-right">
                            {slide.illustration && slide.illustration()}
                          </div>
                        </div>
                        {slide.id === 3 && (
                          <div className="wafa-badge-carousel">
                            <span>Wafa Loyalty</span>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>

                  <button 
                    className="carousel-arrow right" 
                    onClick={() => setCurrentSlide(prev => (prev + 1) % carouselSlides.length)}
                  >
                    <ChevronRight size={18} />
                  </button>

                  <div className="carousel-dots">
                    {carouselSlides.map((_, idx) => (
                      <button 
                        key={idx} 
                        className={`carousel-dot ${currentSlide === idx ? 'active' : ''}`}
                        onClick={() => setCurrentSlide(idx)}
                      />
                    ))}
                  </div>
                </div>
              ) : null}

              {/* Category-specific Banner */}
              {selectedCategory && !searchQuery && categoryBanners[selectedCategory] && (
                <div 
                  className="category-hero-banner" 
                  style={{ 
                    background: categoryBanners[selectedCategory].bg, 
                    borderColor: categoryBanners[selectedCategory].border,
                    color: categoryBanners[selectedCategory].color 
                  }}
                >
                  <h1 style={{ color: categoryBanners[selectedCategory].color }}>
                    {categoryBanners[selectedCategory].title}
                  </h1>
                  <p style={{ color: 'var(--text-normal)' }}>
                    {categoryBanners[selectedCategory].desc}
                  </p>
                </div>
              )}

              {/* Quick Shop by Category Grid (Only on home dashboard or when Categories is clicked in sidebar) */}
              {((!selectedCategory && !searchQuery) || selectedCategory === 'Categories') && (
                <div style={{ marginTop: '24px' }}>
                  <h3 style={{ fontFamily: 'Outfit', fontWeight: 800, color: 'var(--text-bright)', fontSize: '18px', marginBottom: '4px' }}>
                    {selectedCategory === 'Categories' ? 'All Categories' : 'Shop by Category'}
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '0 0 16px 0' }}>
                    {selectedCategory === 'Categories' ? 'Explore all departments at Al Meera Qatar.' : 'Browse fresh food, bakery, beverages, snacks, household items and private labels.'}
                  </p>
                  <div className="category-grid">
                    {[
                      { id: 'Produce', name: 'Fruits & Vegetables', icon: '🥬', count: '9 Items' },
                      { id: 'Dairy', name: 'Dairy, Cheese & Eggs', icon: '🥛', count: '8 Items' },
                      { id: 'Pantry/Grains', name: 'Pantry Staples', icon: '🌾', count: '11 Items' },
                      { id: 'Beverages', name: 'Beverages', icon: '🥤', count: '5 Items' },
                      { id: 'Snacks', name: 'Snacks & Sweets', icon: '🍿', count: '5 Items' },
                      { id: 'Diet', name: 'Healthy Choices', icon: '🥗', count: 'Diet Profiles' },
                      { id: 'Al Meera Products', name: 'Al Meera Products', icon: '🏷️', count: 'Private Label' },
                      { id: 'Bakery', name: 'Bakery & Bread', icon: '🍞', count: 'Fresh Daily' },
                      { id: 'Household', name: 'Household Essentials', icon: '🧻', count: 'Home Care' },
                      { id: 'Baby', name: 'Baby & Personal Care', icon: '🍼', count: 'Baby Care' },
                      { id: 'Pet', name: 'Pet Food & Care', icon: '🐶', count: 'Pet Care' }
                    ].map(cat => (
                      <div key={cat.id} className="category-card" onClick={() => setSelectedCategory(cat.id)}>
                        <span className="category-card-icon">{cat.icon}</span>
                        <h4 className="category-card-title">{cat.name}</h4>
                        <span className="category-card-count">{cat.count}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Super Deals Flyer Section */}
              {!selectedCategory && !searchQuery && (
                (() => {
                  const dealProducts = [...products].filter(p => p.promotion);
                  if (dealProducts.length === 0) return null;
                  return (
                    <div className="deals-section" id="weekly-deals-section">
                      <div className="section-header-deals">
                        <h3 style={{ fontFamily: 'Outfit', fontWeight: 800, color: 'var(--text-bright)', fontSize: '18px', margin: 0 }}>Super Weekly Deals</h3>
                        <span style={{ fontSize: '11px', background: 'var(--secondary-glow)', color: 'var(--secondary)', fontWeight: 700, padding: '3px 8px', borderRadius: '12px', textTransform: 'uppercase' }}>Weekly Flyers</span>
                      </div>
                      <div className="deals-scroll">
                        {dealProducts.map(p => {
                          const discountPct = p.promotion.discount_pct;
                          const finalPrice = p.price * (1 - discountPct);
                          return (
                            <div key={`deal-${p.sku}`} className="deal-card-wrapper">
                              <div className="store-product-card" style={{ margin: 0, width: '100%' }} onClick={() => { setSelectedSku(p.sku); setView('product'); }}>
                                <span className="store-product-discount-badge">{Math.round(discountPct * 100)}% OFF</span>
                                <div className="store-product-image-placeholder" style={{ background: '#fef2f2' }}>
                                  {p.image_url ? (
                                    <img src={p.image_url} alt={p.name} className="store-product-image" />
                                  ) : (
                                    <span style={{ color: 'var(--secondary)', fontSize: '12px', fontWeight: 700 }}>{p.subcategory}</span>
                                  )}
                                </div>
                                <div className="store-product-brand">{p.brand}</div>
                                <div className="store-product-name" style={{ height: '36px', overflow: 'hidden' }}>{p.name}</div>
                                <div className="store-product-price-row">
                                  <div>
                                    <span className="store-product-original-price">{formatPrice(p.price)}</span>
                                    <span className="store-product-price" style={{ color: 'var(--secondary)' }}>{formatPrice(finalPrice)}</span>
                                  </div>
                                  <button className="store-add-btn" style={{ background: 'var(--secondary)' }} onClick={(e) => handleAddToCart(p, e)}>Add</button>
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  );
                })()
              )}

              {/* Wafa Rewards Loyalty Section */}
              {!selectedCategory && !searchQuery && (
                <div className="wafa-rewards-card" id="wafa-rewards-section">
                  <div className="wafa-info">
                    <h3 className="wafa-title">Al Meera WAFA Rewards Club</h3>
                    <p className="wafa-desc">Earn points on every fresh purchase and redeem them instantly for shopping vouchers at any of our branches. Scan your membership barcode at checkout.</p>
                  </div>
                  <div className="wafa-barcode-box">
                    <div className="wafa-barcode">
                      <div className="wafa-barcode-line" style={{ width: '4px' }} />
                      <div className="wafa-barcode-line" style={{ width: '1px' }} />
                      <div className="wafa-barcode-line" style={{ width: '3px' }} />
                      <div className="wafa-barcode-line" style={{ width: '1px' }} />
                      <div className="wafa-barcode-line" style={{ width: '5px' }} />
                      <div className="wafa-barcode-line" style={{ width: '2px' }} />
                      <div className="wafa-barcode-line" style={{ width: '1px' }} />
                      <div className="wafa-barcode-line" style={{ width: '4px' }} />
                      <div className="wafa-barcode-line" style={{ width: '2px' }} />
                      <div className="wafa-barcode-line" style={{ width: '1px' }} />
                      <div className="wafa-barcode-line" style={{ width: '3px' }} />
                      <div className="wafa-barcode-line" style={{ width: '1px' }} />
                    </div>
                    <span className="wafa-barcode-text">974 012 345 678</span>
                  </div>
                </div>
              )}

              {/* Interactive Recipes / Meal Kits Section */}
              {!selectedCategory && !searchQuery && (
                <div className="recipes-section">
                  <h3 style={{ fontFamily: 'Outfit', fontWeight: 800, color: 'var(--text-bright)', fontSize: '18px', marginBottom: '4px' }}>Al Meera Recipes & Meals</h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '0 0 16px 0' }}>Cook authentic recipes using ingredients available straight from our shelves. One-click to add all items.</p>
                  <div className="recipes-grid">
                    {[
                      {
                        title: "Classic Mediterranean Pasta",
                        tag: "Dinner Meal Bundle",
                        ingredients: ["G1", "G3", "P1", "P2", "P5", "G2"],
                        ingredientNames: ["Spaghetti", "Tomato Sauce", "Tomatoes", "Basil", "Garlic", "Olive Oil"],
                        price: 18.44
                      },
                      {
                        title: "Healthy Berry Yogurt Bowl",
                        tag: "Breakfast / Snack",
                        ingredients: ["D3", "P4", "D5"],
                        ingredientNames: ["Greek Yogurt", "Bananas", "Almond Milk"],
                        price: 6.47
                      },
                      {
                        title: "Fresh Avocado Green Salad",
                        tag: "Vegan / Gluten-Free",
                        ingredients: ["P3", "P1", "P7", "G2", "P8"],
                        ingredientNames: ["Spinach", "Tomatoes", "Avocado", "Olive Oil", "Lemon"],
                        price: 22.94
                      }
                    ].map(recipe => (
                      <div key={recipe.title} className="recipe-card">
                        <div className="recipe-header">
                          <span className="recipe-badge">{recipe.tag}</span>
                        </div>
                        <h4 className="recipe-title">{recipe.title}</h4>
                        <div className="recipe-ingredients">
                          {recipe.ingredientNames.map(name => (
                            <span key={name} className="recipe-ingredient-tag">{name}</span>
                          ))}
                        </div>
                        <div className="recipe-action-row">
                          <span className="recipe-price">Bundle Price: {formatPrice(recipe.price)}</span>
                          <button 
                            className="recipe-add-btn"
                            onClick={(e) => handleAddRecipeIngredients(recipe.ingredients, e)}
                          >
                            Get Ingredients
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Title Section & Products Listing */}
              {selectedCategory !== 'Categories' && (
                <>
                  <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '24px' }}>
                    <h2 style={{ fontFamily: 'Outfit', fontWeight: 700, color: 'var(--text-bright)', margin: 0, fontSize: '22px' }}>
                      {selectedCategory ? `${selectedCategory === 'Fresh Food' ? 'Fresh Food' : selectedCategory === 'Qatari Products' ? 'Qatari Products' : selectedCategory} Catalog` : searchQuery ? `Search Results for "${searchQuery}"` : 'Featured Products'}
                    </h2>
                    <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>{products.length} Items Found</span>
                  </div>

                  {products.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px', background: 'white', borderRadius: '16px', border: '1px solid #e5e7eb' }}>
                      <Coffee size={36} style={{ color: 'var(--text-muted)', marginBottom: '8px' }} />
                      <h3 style={{ color: 'var(--text-bright)', margin: 0 }}>No Products Found</h3>
                      <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '4px 0 0 0' }}>Try removing search filters or selecting another category.</p>
                    </div>
                  ) : (
                    <div className="storefront-grid">
                      {products.map(p => {
                        const isOutOfStock = p.stock_qty === 0;
                        const discountPct = p.promotion?.discount_pct || 0;
                        const finalPrice = p.price * (1 - discountPct);
                        
                        return (
                          <div key={p.sku} className="store-product-card" onClick={() => { setSelectedSku(p.sku); setView('product'); }}>
                            
                            {/* Discount Badge */}
                            {discountPct > 0 && (
                              <span className="store-product-discount-badge">{Math.round(discountPct * 100)}% OFF</span>
                            )}

                            {/* Stock Tag */}
                            <span className={`store-product-stock-tag ${isOutOfStock ? 'out-of-stock' : 'in-stock'}`} style={{ color: isOutOfStock ? 'var(--danger)' : 'var(--success)' }}>
                              {isOutOfStock ? 'OOS' : `Stock: ${p.stock_qty}`}
                            </span>

                            {/* Image Placeholder */}
                            <div className="store-product-image-placeholder" style={{ background: p.category === 'Produce' ? '#eefaf2' : p.category === 'Dairy' ? '#eef5fc' : '#fcf5ee' }}>
                              {p.image_url ? (
                                <img src={p.image_url} alt={p.name} className="store-product-image" />
                              ) : (
                                <span style={{ color: p.category === 'Produce' ? '#1b7a3e' : p.category === 'Dairy' ? '#2563eb' : '#d97706', fontSize: '14px' }}>
                                  {p.subcategory}
                                </span>
                              )}
                            </div>

                            {/* Details */}
                            <div className="store-product-brand">{p.brand}</div>
                            <div className="store-product-name">{p.name}</div>
                            
                            {/* Price & Add button */}
                            <div className="store-product-price-row">
                              <div>
                                {discountPct > 0 && (
                                  <span className="store-product-original-price">{formatPrice(p.price)}</span>
                                )}
                                <span className="store-product-price">{formatPrice(finalPrice)}</span>
                              </div>
                              <button 
                                className="store-add-btn" 
                                disabled={isOutOfStock}
                                onClick={(e) => handleAddToCart(p, e)}
                              >
                                Add
                              </button>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {/* B. PRODUCT DETAIL VIEW */}
          {view === 'product' && detailedProduct && (
            <div>
              {/* Back Button */}
              <button 
                onClick={() => setView('home')} 
                style={{ display: 'flex', alignItems: 'center', gap: '6px', background: 'transparent', border: 'none', color: 'var(--primary)', cursor: 'pointer', fontWeight: 600, fontSize: '14px', marginBottom: '24px' }}
              >
                <ArrowLeft size={16} /> Back to Catalog
              </button>

              <div className="product-detail-layout">
                {/* Image Card */}
                <div className="product-detail-img-box" style={{ background: detailedProduct.category === 'Produce' ? '#eefaf2' : detailedProduct.category === 'Dairy' ? '#eef5fc' : '#fcf5ee' }}>
                  {detailedProduct.image_url ? (
                    <img src={detailedProduct.image_url} alt={detailedProduct.name} className="store-product-image" style={{ maxHeight: '100%' }} />
                  ) : (
                    <span style={{ color: detailedProduct.category === 'Produce' ? '#1b7a3e' : detailedProduct.category === 'Dairy' ? '#2563eb' : '#d97706', fontSize: '24px', fontWeight: 700 }}>
                      {detailedProduct.subcategory}
                    </span>
                  )}
                </div>

                {/* Details Section */}
                <div className="product-detail-info">
                  <span style={{ color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    {detailedProduct.brand} | {detailedProduct.category}
                  </span>
                  <h1 style={{ fontFamily: 'Outfit', fontWeight: 800, fontSize: '28px', color: 'var(--text-bright)', margin: '4px 0' }}>
                    {detailedProduct.name}
                  </h1>

                  {/* Price Block */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', margin: '8px 0' }}>
                    {detailedProduct.promotion && (
                      <>
                        <span style={{ textDecoration: 'line-through', color: 'var(--text-muted)', fontSize: '16px' }}>
                          {formatPrice(detailedProduct.price)}
                        </span>
                        <span style={{ background: 'var(--warning)', color: 'white', fontSize: '11px', padding: '2px 6px', borderRadius: '4px', fontWeight: 700 }}>
                          {Math.round(detailedProduct.promotion.discount_pct * 100)}% OFF
                        </span>
                      </>
                    )}
                    <span style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-bright)' }}>
                      {formatPrice(detailedProduct.price * (1 - (detailedProduct.promotion?.discount_pct || 0)))}
                    </span>
                  </div>

                  {/* Stock Grid info */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', background: '#f9fafb', padding: '16px', borderRadius: '12px', border: '1px solid #e5e7eb', fontSize: '13px' }}>
                    <div>
                      <strong style={{ color: 'var(--text-bright)' }}>Online Stock</strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', color: detailedProduct.stock?.online > 0 ? 'var(--success)' : 'var(--danger)' }}>
                        <Globe size={14} /> {detailedProduct.stock?.online > 0 ? `${detailedProduct.stock.online} Units Available` : 'Out of Stock'}
                      </div>
                    </div>
                    <div>
                      <strong style={{ color: 'var(--text-bright)' }}>In-Store Stock</strong>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '4px', color: detailedProduct.stock?.in_store > 0 ? 'var(--success)' : 'var(--danger)' }}>
                        <Store size={14} /> {detailedProduct.stock?.in_store > 0 ? `${detailedProduct.stock.in_store} Units Available` : 'Out of Stock'}
                      </div>
                    </div>
                  </div>

                  {/* Customer Preference Warning Card */}
                  {getProductWarnings(detailedProduct).map((warning, index) => (
                    <div key={index} className="product-detail-allergy-warning">
                      <ShieldAlert size={18} />
                      <span>{warning}</span>
                    </div>
                  ))}

                  {/* Add to Cart CTA */}
                  <button 
                    className="hero-banner-btn" 
                    style={{ width: '100%', padding: '14px', fontSize: '16px', borderRadius: '12px' }}
                    disabled={detailedProduct.stock?.[channel] === 0}
                    onClick={() => handleAddToCart(detailedProduct)}
                  >
                    {detailedProduct.stock?.[channel] === 0 ? 'Currently Out of Stock' : 'Add to Shopping Cart'}
                  </button>

                  {/* Alternative suggestions */}
                  {detailedProduct.alternatives && detailedProduct.alternatives.length > 0 && (
                    <div style={{ marginTop: '24px' }}>
                      <h4 style={{ color: 'var(--text-bright)', margin: '0 0 12px 0', borderBottom: '1px solid #e5e7eb', paddingBottom: '6px' }}>
                        Suggestions
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                        {detailedProduct.alternatives.map(alt => (
                          <div 
                            key={alt.sku} 
                            style={{ padding: '12px', border: '1px solid #e5e7eb', borderRadius: '8px', cursor: 'pointer', background: 'white', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                            onClick={() => { setSelectedSku(alt.sku); }}
                          >
                            <div>
                              <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-bright)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', maxWidth: '140px' }}>{alt.name}</div>
                              <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginTop: '2px' }}>{formatPrice(alt.price)}</div>
                            </div>
                            <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                </div>
              </div>
            </div>
          )}

          </div>
          
          {/* FOOTER */}
          <footer className="footer-almeera">
            <div className="footer-content">
              <div className="footer-grid">
                
                {/* Column 1: Brand Info */}
                <div className="footer-col brand-col">
                  <AlMeeraLogo />
                  <p className="footer-brand-desc">
                    Qatar's leading consumer goods company, dedicated to providing high-quality products and fresh foods at the best value.
                  </p>
                  <div className="footer-socials">
                    <span className="social-icon">🔵</span>
                    <span className="social-icon">📸</span>
                    <span className="social-icon">🐦</span>
                    <span className="social-icon">💼</span>
                  </div>
                </div>

                {/* Column 2: Company */}
                <div className="footer-col">
                  <h4>Company</h4>
                  <ul>
                    <li><a href="#about" onClick={(e) => e.preventDefault()}>About Al Meera</a></li>
                    <li><a href="#board" onClick={(e) => e.preventDefault()}>Board of Directors</a></li>
                    <li><a href="#message" onClick={(e) => e.preventDefault()}>Chairman's Message</a></li>
                    <li><a href="#careers" onClick={(e) => e.preventDefault()}>Careers</a></li>
                    <li><a href="#news" onClick={(e) => e.preventDefault()}>Latest News</a></li>
                  </ul>
                </div>

                {/* Column 3: Customer Services */}
                <div className="footer-col">
                  <h4>Customer Services</h4>
                  <ul>
                    <li><a href="#locator" onClick={(e) => e.preventDefault()}>Store Locator</a></li>
                    <li><a href="#wafa" onClick={(e) => e.preventDefault()}>WAFA Rewards</a></li>
                    <li><a href="#faqs" onClick={(e) => e.preventDefault()}>FAQs</a></li>
                    <li><a href="#refund" onClick={(e) => e.preventDefault()}>Refund Policy</a></li>
                    <li><a href="#terms" onClick={(e) => e.preventDefault()}>Terms & Conditions</a></li>
                  </ul>
                </div>

                {/* Column 4: Contact Us */}
                <div className="footer-col contact-col">
                  <h4>Contact Us</h4>
                  <p><strong>Phone:</strong> +974 4011 9011</p>
                  <p><strong>Email:</strong> customerservice@almeera.com.qa</p>
                  <p><strong>Address:</strong> Rafal Tower, Floor 17, Lusail, Qatar</p>
                  
                  <div className="app-download-badges" style={{ marginTop: '16px', display: 'flex', gap: '8px' }}>
                    <div className="app-badge">
                      <span style={{ fontSize: '10px', display: 'block', opacity: 0.7 }}>Download on the</span>
                      <strong style={{ fontSize: '12px' }}>App Store</strong>
                    </div>
                    <div className="app-badge">
                      <span style={{ fontSize: '10px', display: 'block', opacity: 0.7 }}>Get it on</span>
                      <strong style={{ fontSize: '12px' }}>Google Play</strong>
                    </div>
                  </div>
                </div>

              </div>
              
              <div className="footer-bottom">
                <p>© 2026 Al Meera Consumer Goods Company (Q.P.S.C). All rights reserved.</p>
              </div>
            </div>
          </footer>
        </div>
      </div>

      {/* 4. CART SLIDING DRAWER CONTAINER */}
      {isCartOpen && (
        <>
          <div className="cart-drawer-overlay" onClick={() => setIsCartOpen(false)} />
          <div className="cart-drawer">
            <div className="cart-drawer-header">
              <span className="cart-drawer-title">Shopping Cart</span>
              <button style={{ background: 'transparent', border: 'none', cursor: 'pointer' }} onClick={() => setIsCartOpen(false)}>
                <X size={20} style={{ color: 'var(--text-muted)' }} />
              </button>
            </div>

            <div className="cart-drawer-items">
              {cart.length === 0 ? (
                <div style={{ textAlign: 'center', marginTop: '100px', color: 'var(--text-muted)' }}>
                  <ShoppingCart size={48} style={{ margin: '0 auto 16px auto', opacity: 0.5 }} />
                  <div>Your shopping cart is empty.</div>
                  <button className="hero-banner-btn" style={{ margin: '16px auto 0 auto', fontSize: '13px' }} onClick={() => setIsCartOpen(false)}>Browse Catalog</button>
                </div>
              ) : (
                cart.map(item => {
                  const discountPct = item.product.promotion?.discount_pct || 0;
                  const finalPrice = item.product.price * (1 - discountPct);
                  
                  return (
                    <div key={item.product.sku} className="cart-item">
                      <div className="cart-item-info">
                        <span className="cart-item-name">{item.product.name}</span>
                        <span className="cart-item-qty">{item.product.brand}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <button style={{ border: '1px solid #d1d5db', background: 'white', borderRadius: '4px', width: '22px', height: '22px', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => handleUpdateCartQty(item.product.sku, -1)}>-</button>
                        <span style={{ fontWeight: 600, fontSize: '14px', minWidth: '16px', textAlign: 'center' }}>{item.qty}</span>
                        <button style={{ border: '1px solid #d1d5db', background: 'white', borderRadius: '4px', width: '22px', height: '22px', cursor: 'pointer', fontWeight: 'bold' }} onClick={() => handleUpdateCartQty(item.product.sku, 1)}>+</button>
                      </div>
                      <span className="cart-item-price">{formatPrice(finalPrice * item.qty)}</span>
                      <button style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }} onClick={() => handleRemoveFromCart(item.product.sku)}>
                        <X size={14} />
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {cart.length > 0 && (
              <div className="cart-drawer-footer">
                <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 'bold', fontSize: '16px' }}>
                  <span style={{ color: 'var(--text-muted)' }}>Subtotal</span>
                  <span style={{ color: 'var(--text-bright)' }}>{formatPrice(cartSubtotal)}</span>
                </div>
                <button className="hero-banner-btn" style={{ width: '100%', padding: '12px' }} onClick={() => alert(`Checked out successfully! Total: ${formatPrice(cartSubtotal)}`)}>
                  Proceed to Checkout
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* 5. FLOATING CHAT LAUNCHER WIDGET BUTTON */}
      <button className="chat-launcher-btn" onClick={() => setIsChatOpen(!isChatOpen)}>
        {isChatOpen ? <X size={26} /> : <MessageSquare size={26} />}
      </button>

      {/* 6. FLOATING CHAT WIDGET POPUP PANEL */}
      {isChatOpen && (
        <div className="chat-widget-panel">
          <div className="chat-widget-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <MessageSquare size={18} />
              <span className="chat-widget-title">Al Meera Shopping Assistant</span>
            </div>
            <button className="chat-widget-close" onClick={() => setIsChatOpen(false)}>
              <X size={18} />
            </button>
          </div>

          <div className="chat-widget-body">
            
            {/* Messages Scroll Area */}
            <div className="messages-scroller" style={{ background: '#f9fafb' }}>
              {messages.length === 0 && (
                <div style={{ margin: 'auto', textAlign: 'center', maxWidth: '300px', padding: '40px 10px' }}>
                  <Coffee size={36} style={{ color: 'var(--primary)', marginBottom: '12px', opacity: 0.8 }} />
                  <h3 style={{ fontFamily: 'Outfit', fontWeight: 600, color: 'var(--text-bright)', marginBottom: '6px' }}>
                    How can I help you today?
                  </h3>
                  <p style={{ color: 'var(--text-muted)', fontSize: '13px', lineHeight: 1.5 }}>
                    Ask me to search for grocery items, suggest recipes, check store promotions, or suggest alternatives.
                  </p>
                </div>
              )}

              {messages.map((msg, index) => (
                <div key={index} className={`message-wrapper ${msg.sender}`}>
                  <div className="bubble">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontSize: '11px', color: msg.sender === 'user' ? 'rgba(255, 255, 255, 0.85)' : 'var(--text-muted)' }}>
                      <User size={12} />
                      <span>{msg.sender === 'user' ? 'Customer' : 'AI Assistant'}</span>
                      <span>•</span>
                      <span>{msg.timestamp}</span>
                    </div>
                    <div className="chat-text-content">
                      {renderMarkdown(msg.text)}
                    </div>

                    {/* RENDER PRODUCTS INSIDE CHAT FOR EASY CART ACTION */}
                    {msg.sender === 'bot' && msg.structured && (
                      <div className="products-container">
                        {msg.structured.enrichment_timed_out && (
                          <div className="discount-banner" style={{ background: 'rgba(239, 68, 68, 0.08)', borderColor: 'rgba(239, 68, 68, 0.15)', color: '#b91c1c', marginBottom: '8px', width: 'fit-content' }}>
                            <AlertCircle size={10} />
                            <span>Enrichment Search Timed Out (Partial Data)</span>
                          </div>
                        )}

                        {/* Primary Matches */}
                        {msg.structured.primary_skus && msg.structured.primary_skus.length > 0 && (
                          <div>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                              Primary Matches
                            </div>
                            <div className="compact-products-list">
                              {msg.structured.primary_skus.map(sku => {
                                const p = msg.products?.[sku];
                                if (!p) return null;
                                const isOutOfStock = p.stock?.[channel] === 0;
                                const promo = p.promotion;
                                const discountPct = promo?.discount_pct || 0;
                                const finalPrice = p.price * (1 - discountPct);
                                
                                return (
                                  <div key={sku} className="compact-product-row" onClick={() => { setSelectedSku(sku); setView('product'); setIsChatOpen(false); }}>
                                    <div className="compact-row-left">
                                      <span className="compact-brand">{p.brand}</span>
                                      <div className="compact-name-row">
                                        <span className={`compact-stock-dot ${isOutOfStock ? 'out-of-stock' : 'in-stock'}`} title={isOutOfStock ? "Out of Stock" : `Stock: ${p.stock?.[channel]}`} />
                                        <span className="compact-name" title={p.name}>{p.name}</span>
                                      </div>
                                    </div>
                                    <div className="compact-row-right">
                                      <div className="compact-price-box">
                                        {discountPct > 0 && (
                                          <span className="compact-original-price">{formatPrice(p.price)}</span>
                                        )}
                                        <span className="compact-price">{formatPrice(finalPrice)}</span>
                                      </div>
                                      <button className="compact-add-btn" disabled={isOutOfStock} onClick={(e) => { e.stopPropagation(); handleAddToCart({ ...p, stock_qty: p.stock?.[channel] }); }}>
                                        <Plus size={12} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Personalized Recommendations */}
                        {msg.structured.recommended_skus && msg.structured.recommended_skus.length > 0 && (
                          <div style={{ marginTop: '12px' }}>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--rec-violet)', textTransform: 'uppercase', marginBottom: '6px' }}>
                              Personalized For You
                            </div>
                            <div className="compact-products-list">
                              {msg.structured.recommended_skus.map(sku => {
                                const p = msg.products?.[sku];
                                if (!p) return null;
                                const isOutOfStock = p.stock?.[channel] === 0;
                                const promo = p.promotion;
                                const discountPct = promo?.discount_pct || 0;
                                const finalPrice = p.price * (1 - discountPct);
                                
                                return (
                                  <div key={sku} className="compact-product-row personalized" onClick={() => { setSelectedSku(sku); setView('product'); setIsChatOpen(false); }}>
                                    <div className="compact-row-left">
                                      <span className="compact-brand">{p.brand}</span>
                                      <div className="compact-name-row">
                                        <span className={`compact-stock-dot ${isOutOfStock ? 'out-of-stock' : 'in-stock'}`} title={isOutOfStock ? "Out of Stock" : `Stock: ${p.stock?.[channel]}`} />
                                        <span className="compact-name" title={p.name}>{p.name}</span>
                                      </div>
                                    </div>
                                    <div className="compact-row-right">
                                      <div className="compact-price-box">
                                        {discountPct > 0 && (
                                          <span className="compact-original-price">{formatPrice(p.price)}</span>
                                        )}
                                        <span className="compact-price">{formatPrice(finalPrice)}</span>
                                      </div>
                                      <button className="compact-add-btn" disabled={isOutOfStock} onClick={(e) => { e.stopPropagation(); handleAddToCart({ ...p, stock_qty: p.stock?.[channel] }); }}>
                                        <Plus size={12} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* Frequently Bought Together */}
                        {msg.structured.affinity_skus && msg.structured.affinity_skus.length > 0 && (
                          <div style={{ marginTop: '12px' }}>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--aff-orange)', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Flame size={12} />
                              <span>Frequently Bought Together</span>
                            </div>
                            <div className="compact-products-list">
                              {msg.structured.affinity_skus.map(sku => {
                                const p = msg.products?.[sku];
                                if (!p) return null;
                                const isOutOfStock = p.stock?.[channel] === 0;
                                const promo = p.promotion;
                                const discountPct = promo?.discount_pct || 0;
                                const finalPrice = p.price * (1 - discountPct);
                                
                                return (
                                  <div key={sku} className="compact-product-row combo" onClick={() => { setSelectedSku(sku); setView('product'); setIsChatOpen(false); }}>
                                    <div className="compact-row-left">
                                      <span className="compact-brand">{p.brand}</span>
                                      <div className="compact-name-row">
                                        <span className={`compact-stock-dot ${isOutOfStock ? 'out-of-stock' : 'in-stock'}`} title={isOutOfStock ? "Out of Stock" : `Stock: ${p.stock?.[channel]}`} />
                                        <span className="compact-name" title={p.name}>{p.name}</span>
                                      </div>
                                    </div>
                                    <div className="compact-row-right">
                                      <div className="compact-price-box">
                                        {discountPct > 0 && (
                                          <span className="compact-original-price">{formatPrice(p.price)}</span>
                                        )}
                                        <span className="compact-price">{formatPrice(finalPrice)}</span>
                                      </div>
                                      <button className="compact-add-btn" disabled={isOutOfStock} onClick={(e) => { e.stopPropagation(); handleAddToCart({ ...p, stock_qty: p.stock?.[channel] }); }}>
                                        <Plus size={12} />
                                      </button>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        )}

                      </div>
                    )}

                  </div>
                </div>
              ))}

              {loading && (
                <div className="message-wrapper bot">
                  <div className="bubble">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', fontSize: '11px', color: 'var(--text-muted)' }}>
                      <User size={12} />
                      <span>AI Assistant</span>
                    </div>
                    <div className="typing-indicator">
                      <span className="dot"></span>
                      <span className="dot"></span>
                      <span className="dot"></span>
                    </div>
                  </div>
                </div>
              )}
              
              <div ref={messagesEndRef} />
            </div>

            {/* Chat Input Bar */}
            <form onSubmit={handleSendMessage} className="input-area" style={{ padding: '12px 16px' }}>
              <div className="input-container">
                <input 
                  type="text" 
                  placeholder="Type a message or recipe query..."
                  className="chat-input"
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  disabled={loading}
                />
                <button type="submit" className="send-btn" disabled={!query.trim() || loading}>
                  <Send size={16} />
                </button>
              </div>
            </form>

          </div>
        </div>
      )}

    </div>
  );
}

export default App;
