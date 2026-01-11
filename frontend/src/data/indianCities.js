/**
 * Indian Cities Data
 * 
 * Comprehensive list of major Indian cities for autocomplete functionality.
 * Cities are organized alphabetically for efficient filtering.
 */

export const INDIAN_CITIES = [
  'Agra',
  'Ahmedabad',
  'Ajmer',
  'Akola',
  'Aligarh',
  'Allahabad',
  'Amravati',
  'Amritsar',
  'Anand',
  'Aurangabad',
  'Bangalore',
  'Bareilly',
  'Belgaum',
  'Bhavnagar',
  'Bhopal',
  'Bhubaneswar',
  'Bikaner',
  'Bilaspur',
  'Bokaro',
  'Chandigarh',
  'Chennai',
  'Coimbatore',
  'Cuttack',
  'Dehradun',
  'Delhi',
  'Dhanbad',
  'Dharwad',
  'Durgapur',
  'Faridabad',
  'Gandhinagar',
  'Gaya',
  'Ghaziabad',
  'Gorakhpur',
  'Gulbarga',
  'Guntur',
  'Gurgaon',
  'Guwahati',
  'Gwalior',
  'Hajipur',
  'Haldia',
  'Hubli',
  'Hyderabad',
  'Indore',
  'Jabalpur',
  'Jaipur',
  'Jalandhar',
  'Jammu',
  'Jamnagar',
  'Jamshedpur',
  'Jhansi',
  'Jodhpur',
  'Kakinada',
  'Kalyan',
  'Kanpur',
  'Karnal',
  'Kochi',
  'Kolhapur',
  'Kolkata',
  'Kollam',
  'Kota',
  'Kozhikode',
  'Kurnool',
  'Lucknow',
  'Ludhiana',
  'Madurai',
  'Mangalore',
  'Meerut',
  'Mumbai',
  'Mysore',
  'Nagpur',
  'Nashik',
  'Navi Mumbai',
  'Nellore',
  'Noida',
  'Panaji',
  'Patna',
  'Pimpri-Chinchwad',
  'Pondicherry',
  'Pune',
  'Raipur',
  'Rajkot',
  'Ranchi',
  'Rourkela',
  'Salem',
  'Sangli',
  'Shimla',
  'Siliguri',
  'Solapur',
  'Srinagar',
  'Surat',
  'Thane',
  'Thiruvananthapuram',
  'Thrissur',
  'Tiruchirappalli',
  'Tirunelveli',
  'Udaipur',
  'Ujjain',
  'Vadodara',
  'Varanasi',
  'Vasai-Virar',
  'Vellore',
  'Vijayawada',
  'Visakhapatnam',
  'Warangal'
];

/**
 * Filter cities based on search query
 * @param {string} query - Search query (case-insensitive)
 * @param {number} maxResults - Maximum number of results to return (default: 10)
 * @returns {string[]} Array of matching city names
 */
export const filterCities = (query, maxResults = 10) => {
  if (!query || query.trim().length === 0) {
    return [];
  }
  
  const searchQuery = query.trim().toLowerCase();
  const matches = INDIAN_CITIES.filter(city => 
    city.toLowerCase().startsWith(searchQuery)
  );
  
  return matches.slice(0, maxResults);
};



















