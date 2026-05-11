/**
 * Dashboard Analytics Module
 * Handles animations, charts, and interactivity for the admin dashboard
 */

(function() {
  'use strict';

  var dashboardInitialized = false;

  /**
   * Initialize dashboard animations and charts
   */
  function initializeDashboard(statsData) {
    if (dashboardInitialized) {
      return;
    }
    dashboardInitialized = true;

    console.log('Initializing dashboard with stats:', statsData);
    animateMetricCards();
    animateEngagementCards();
    animateActivityItems();
    animateNewDataItems();
    updateActiveUsersCard(statsData);
    initializeDailyUsersChart(statsData);
    initializeGrowthTrendChart(statsData);
    initializeOnlineIndicator();
    attachMetricCardHoverEffects();
    attachEngagementCardEffects();
    attachScrollAnimations();
  }

  /**
   * Animate metric cards with staggered entrance
   */
  function animateMetricCards() {
    var metricCards = document.querySelectorAll('.metric-card');
    metricCards.forEach(function(card, index) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(20px)';
      setTimeout(function() {
        card.style.transition = 'all 0.5s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      }, index * 100);
    });
  }

  /**
   * Animate engagement cards
   */
  function animateEngagementCards() {
    var engagementCards = document.querySelectorAll('.engagement-card');
    engagementCards.forEach(function(card, index) {
      card.style.opacity = '0';
      card.style.transform = 'translateY(20px)';
      setTimeout(function() {
        card.style.transition = 'all 0.5s ease';
        card.style.opacity = '1';
        card.style.transform = 'translateY(0)';
      }, 500 + (index * 100));
    });
  }

  /**
   * Animate activity list items
   */
  function animateActivityItems() {
    var activityItems = document.querySelectorAll('.activity-card li:not(.empty-activity)');
    activityItems.forEach(function(item, index) {
      item.style.opacity = '0';
      item.style.transform = 'translateX(-20px)';
      setTimeout(function() {
        item.style.transition = 'all 0.4s ease';
        item.style.opacity = '1';
        item.style.transform = 'translateX(0)';
      }, index * 80);
    });
  }

  /**
   * Animate new data items
   */
  function animateNewDataItems() {
    var newDataItems = document.querySelectorAll('.new-data-item');
    newDataItems.forEach(function(item, index) {
      item.style.opacity = '0';
      item.style.transform = 'translateX(20px)';
      setTimeout(function() {
        item.style.transition = 'all 0.4s ease';
        item.style.opacity = '1';
        item.style.transform = 'translateX(0)';
      }, 500 + (index * 100));
    });
  }

  /**
   * Initialize daily users bar chart
   * @param {Object} statsData - Statistics data object
   */
  function initializeDailyUsersChart(statsData) {
    var dailyUsersCtx = document.getElementById('dailyUsersChart');
    if (!dailyUsersCtx || typeof Chart === 'undefined') {
      console.warn('Daily users chart: Canvas not found or Chart.js not loaded');
      return;
    }

    try {
      var dailyUsersData = statsData.daily_users || {};
      console.log('Daily users data:', dailyUsersData);
      var dailyLabels = Object.keys(dailyUsersData);
      var dailyValues = Object.values(dailyUsersData);
      console.log('Daily labels:', dailyLabels, 'Values:', dailyValues);

      new Chart(dailyUsersCtx, {
        type: 'bar',
        data: {
          labels: dailyLabels,
          datasets: [{
            label: 'New Users',
            data: dailyValues,
            backgroundColor: 'rgba(139, 92, 246, 0.7)',
            borderColor: '#8b5cf6',
            borderWidth: 2,
            borderRadius: 8,
            hoverBackgroundColor: 'rgba(139, 92, 246, 0.9)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: {
            padding: {
              top: 10,
              right: 10,
              bottom: 10,
              left: 10
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              padding: window.innerWidth <= 768 ? 8 : 12,
              titleFont: {
                size: window.innerWidth <= 768 ? 11 : 13,
                weight: 'bold'
              },
              bodyFont: { size: window.innerWidth <= 768 ? 10 : 12 },
              borderColor: '#8b5cf6',
              borderWidth: 1,
              cornerRadius: 8,
              displayColors: false
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                color: '#9ca3af',
                font: {
                  size: window.innerWidth <= 768 ? 10 : 12
                },
                padding: window.innerWidth <= 480 ? 5 : 10
              },
              grid: { color: 'rgba(0, 0, 0, 0.05)' }
            },
            x: {
              ticks: {
                color: '#9ca3af',
                font: {
                  size: window.innerWidth <= 768 ? 10 : 12
                },
                maxRotation: window.innerWidth <= 480 ? 45 : 0,
                padding: window.innerWidth <= 480 ? 5 : 10
              },
              grid: { color: 'rgba(0, 0, 0, 0.05)' }
            }
          },
          interaction: {
            mode: 'index',
            intersect: false
          },
          elements: {
            bar: {
              borderRadius: window.innerWidth <= 480 ? 4 : 8
            }
          }
        }
      });
    } catch (error) {
      console.error('Error initializing daily users chart:', error);
    }
  }

  /**
   * Initialize user growth trend line chart
   * @param {Object} statsData - Statistics data object
   */
  function initializeGrowthTrendChart(statsData) {
    var growthTrendCtx = document.getElementById('growthTrendChart');
    if (!growthTrendCtx || typeof Chart === 'undefined') {
      console.warn('Growth trend chart: Canvas not found or Chart.js not loaded');
      return;
    }

    try {
      var growthTrendData = statsData.user_growth_trend || {};
      console.log('Growth trend data:', growthTrendData);
      var growthLabels = Object.keys(growthTrendData);
      var growthValues = Object.values(growthTrendData);
      console.log('Growth labels:', growthLabels, 'Values:', growthValues);

      new Chart(growthTrendCtx, {
        type: 'line',
        data: {
          labels: growthLabels,
          datasets: [{
            label: 'Total Users',
            data: growthValues,
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            borderColor: '#3b82f6',
            borderWidth: 3,
            fill: true,
            tension: 0.4,
            pointBackgroundColor: '#3b82f6',
            pointBorderColor: 'white',
            pointBorderWidth: 2,
            pointRadius: 5,
            pointHoverRadius: 7
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          layout: {
            padding: {
              top: 10,
              right: 10,
              bottom: 10,
              left: 10
            }
          },
          plugins: {
            legend: {
              display: window.innerWidth > 480,
              labels: {
                font: {
                  size: window.innerWidth <= 768 ? 11 : 12
                }
              }
            },
            tooltip: {
              backgroundColor: 'rgba(0, 0, 0, 0.8)',
              padding: window.innerWidth <= 768 ? 8 : 12,
              titleFont: {
                size: window.innerWidth <= 768 ? 11 : 13,
                weight: 'bold'
              },
              bodyFont: { size: window.innerWidth <= 768 ? 10 : 12 },
              borderColor: '#8b5cf6',
              borderWidth: 1,
              cornerRadius: 8,
              displayColors: true
            }
          },
          scales: {
            y: {
              beginAtZero: true,
              ticks: {
                color: '#9ca3af',
                font: {
                  size: window.innerWidth <= 768 ? 10 : 12
                },
                padding: window.innerWidth <= 480 ? 5 : 10
              },
              grid: { color: 'rgba(0, 0, 0, 0.05)' }
            },
            x: {
              ticks: {
                color: '#9ca3af',
                font: {
                  size: window.innerWidth <= 768 ? 10 : 12
                },
                maxRotation: window.innerWidth <= 480 ? 45 : 0,
                padding: window.innerWidth <= 480 ? 5 : 10
              },
              grid: { color: 'rgba(0, 0, 0, 0.05)' }
            }
          },
          interaction: {
            mode: 'index',
            intersect: false
          },
          elements: {
            point: {
              radius: window.innerWidth <= 480 ? 3 : 5,
              hoverRadius: window.innerWidth <= 480 ? 5 : 7
            },
            line: {
              borderWidth: window.innerWidth <= 480 ? 2 : 3
            }
          }
        }
      });
    } catch (error) {
      console.error('Error initializing growth trend chart:', error);
    }
  }

  /**
   * Update active users card value from stats data
   */
  function updateActiveUsersCard(statsData) {
    var activeUsersElement = document.getElementById('activeUsersValue');
    if (!activeUsersElement) {
      return;
    }
    var activeUsers = typeof statsData.active_users !== 'undefined' ? statsData.active_users : statsData.activeUsers;
    activeUsersElement.textContent = activeUsers != null ? activeUsers : '0';
  }

  /**
   * Initialize real-time online users indicator pulse
   */
  function initializeOnlineIndicator() {
    var onlineElements = document.querySelectorAll('.engagement-card .engagement-value');
    if (onlineElements.length > 0) {
      var firstElement = onlineElements[0];
      setInterval(function() {
        firstElement.style.textShadow = '0 0 10px rgba(34, 197, 94, 0.6)';
        setTimeout(function() {
          firstElement.style.textShadow = 'none';
        }, 500);
      }, 2000);
    }
  }

  /**
   * Attach hover effects to metric cards
   */
  function attachMetricCardHoverEffects() {
    var allMetricCards = document.querySelectorAll('.metric-card');
    allMetricCards.forEach(function(card) {
      card.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-4px)';
      });
      card.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
      });
    });
  }

  /**
   * Attach hover effects to engagement cards
   */
  function attachEngagementCardEffects() {
    var allEngagementCards = document.querySelectorAll('.engagement-card');
    allEngagementCards.forEach(function(card) {
      card.addEventListener('mouseenter', function() {
        this.style.transform = 'translateY(-4px)';
        this.style.boxShadow = '0 12px 24px rgba(139, 92, 246, 0.15)';
      });
      card.addEventListener('mouseleave', function() {
        this.style.transform = 'translateY(0)';
        this.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.06)';
      });
    });
  }

  /**
   * Attach scroll-based animations to chart containers
   */
  function attachScrollAnimations() {
    var chartContainers = document.querySelectorAll('.chart-container');
    var observerOptions = {
      threshold: 0.3,
      rootMargin: '0px'
    };

    var observer = new IntersectionObserver(function(entries) {
      entries.forEach(function(entry) {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'translateY(0)';
        }
      });
    }, observerOptions);

    chartContainers.forEach(function(container) {
      container.style.opacity = '0';
      container.style.transform = 'translateY(20px)';
      container.style.transition = 'all 0.6s ease';
      observer.observe(container);
    });
  }

  /**
   * Handle window resize for dynamic chart updates
   */
  function handleResize() {
    // Charts will automatically resize due to responsive: true
    // Additional resize logic can be added here if needed
  }

  /**
   * Attach resize event listener
   */
  function attachResizeListener() {
    var resizeTimeout;
    window.addEventListener('resize', function() {
      clearTimeout(resizeTimeout);
      resizeTimeout = setTimeout(handleResize, 250);
    });
  }

  /**
   * Initialize dashboard when DOM is ready
   */
  document.addEventListener('DOMContentLoaded', function() {
    // Get stats data from window object (injected by template)
    var statsData = window.dashboardStats || {};
    console.log('DOMContentLoaded: Stats data available:', !!Object.keys(statsData).length);
    initializeDashboard(statsData);
    attachResizeListener();
  });

  // Expose initializeDashboard globally for external initialization
  window.initializeDashboard = initializeDashboard;

})();
